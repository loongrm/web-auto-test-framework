pipeline {
    agent any

    environment {
        IMAGE_NAME    = "auto-test-platform"
        IMAGE_TAG     = "${IMAGE_NAME}:${BUILD_NUMBER}"
        ALLURE_DIR    = "reports/allure-results"
        PLATFORM_URL  = "http://your-server:5173"
        ALLURE_URL    = "http://your-server:5050"
    }

    parameters {
        choice(
            name: 'PIPELINE_TYPE',
            choices: ['single', 'multi-env', 'smoke-only'],
            description: '流水线类型：single=单环境, multi-env=多环境并行, smoke-only=仅冒烟'
        )
        choice(name: 'MODULE',  choices: ['all', 'ui', 'api'], description: '测试模块')
        choice(name: 'ENV',     choices: ['dev', 'test', 'prod'], description: '单环境模式使用')
        string(name: 'MARKERS', defaultValue: '',               description: 'pytest 标签过滤')
    }

    triggers {
        // 每晚02:00全量回归（test环境）
        cron('0 2 * * *')
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    echo "Commit: ${env.GIT_SHORT}"
                }
            }
        }

        stage('Build Image') {
            steps {
                sh "docker build -t ${IMAGE_TAG} ."
            }
        }

        // 单环境模式
        stage('Run Tests - Single') {
            when { expression { params.PIPELINE_TYPE == 'single' } }
            steps {
                script {
                    runTestsInDocker(
                        imageTag:  env.IMAGE_TAG,
                        module:    params.MODULE,
                        env:       params.ENV,
                        markers:   params.MARKERS,
                        reportDir: env.ALLURE_DIR
                    )
                }
            }
        }

        // 多环境并行模式
        stage('Run Tests - Multi-Env') {
            when { expression { params.PIPELINE_TYPE == 'multi-env' } }
            parallel {
                stage('DEV') {
                    steps {
                        script {
                            runTestsInDocker(
                                imageTag:  env.IMAGE_TAG,
                                module:    'all',
                                env:       'dev',
                                markers:   'smoke',
                                reportDir: 'reports/allure-results-dev'
                            )
                        }
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'reports/allure-results-dev/**', allowEmptyArchive: true
                        }
                    }
                }
                stage('TEST') {
                    steps {
                        script {
                            runTestsInDocker(
                                imageTag:  env.IMAGE_TAG,
                                module:    'all',
                                env:       'test',
                                markers:   '',
                                reportDir: 'reports/allure-results-test'
                            )
                        }
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'reports/allure-results-test/**', allowEmptyArchive: true
                        }
                    }
                }
            }
        }

        // 冒烟测试模式
        stage('Run Tests - Smoke') {
            when { expression { params.PIPELINE_TYPE == 'smoke-only' } }
            steps {
                script {
                    runTestsInDocker(
                        imageTag:  env.IMAGE_TAG,
                        module:    'all',
                        env:       params.ENV,
                        markers:   'smoke',
                        reportDir: env.ALLURE_DIR
                    )
                }
            }
        }

        stage('Generate Allure Report') {
            steps {
                script {
                    // 多环境时合并主报告目录
                    if (params.PIPELINE_TYPE == 'multi-env') {
                        sh """
                            mkdir -p ${env.ALLURE_DIR}
                            cp -r reports/allure-results-dev/* ${env.ALLURE_DIR}/ 2>/dev/null || true
                            cp -r reports/allure-results-test/* ${env.ALLURE_DIR}/ 2>/dev/null || true
                        """
                    }
                }
                allure([results: [[path: env.ALLURE_DIR]]])
            }
        }

        stage('Notify: Start AI Summary') {
            steps {
                script {
                    // 调用后端AI摘要接口（异步，不阻塞流水线）
                    sh """
                        curl -s -X POST http://localhost:8000/api/runner/run \\
                            -H 'Content-Type: application/json' \\
                            -d '{"module":"all","env":"${params.ENV}","trigger":"jenkins"}' \\
                            || true
                    """
                }
            }
        }
    }

    post {
        success {
            script {
                sendWeChatNotification(
                    status:      'success',
                    buildNumber: env.BUILD_NUMBER,
                    pipelineType: params.PIPELINE_TYPE,
                    module:      params.MODULE,
                    env:         params.ENV,
                    gitCommit:   env.GIT_SHORT,
                    platformUrl: env.PLATFORM_URL,
                    allureUrl:   env.ALLURE_URL,
                )
            }
        }
        failure {
            script {
                sendWeChatNotification(
                    status:      'failure',
                    buildNumber: env.BUILD_NUMBER,
                    pipelineType: params.PIPELINE_TYPE,
                    module:      params.MODULE,
                    env:         params.ENV,
                    gitCommit:   env.GIT_SHORT,
                    platformUrl: env.PLATFORM_URL,
                    allureUrl:   env.ALLURE_URL,
                )
            }
            emailext(
                subject: "❌ [${JOB_NAME}] #${BUILD_NUMBER} 测试失败",
                body: """
<h2>自动化测试失败</h2>
<p>构建号: ${BUILD_NUMBER} | 模块: ${params.MODULE} | 环境: ${params.ENV}</p>
<p><a href="${BUILD_URL}allure">查看 Allure 报告</a></p>
<p><a href="${env.PLATFORM_URL}">查看测试平台看板</a></p>
                """,
                mimeType: 'text/html',
                to: "${TEAM_EMAIL}"
            )
        }
        always {
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
            archiveArtifacts artifacts: 'screenshots/**,logs/**', allowEmptyArchive: true
            sh "docker rmi ${IMAGE_TAG} || true"
        }
    }
}

// 共用函数：在Docker内运行测试
def runTestsInDocker(Map args) {
    def testPath = args.module == 'all' ? 'tests/' : "tests/${args.module}"
    def markerArg = args.markers ? "-m '${args.markers}'" : ''

    sh """
        mkdir -p ${args.reportDir} reports logs screenshots
        docker run --rm \\
            --name test-${args.env}-${BUILD_NUMBER} \\
            -v \$(pwd)/${args.reportDir}:/app/${args.reportDir} \\
            -v \$(pwd)/reports:/app/reports \\
            -v \$(pwd)/logs:/app/logs \\
            -v \$(pwd)/screenshots:/app/screenshots \\
            --env-file .env \\
            -e TEST_ENV=${args.env} \\
            -e PYTHONPATH=/app \\
            ${args.imageTag} \\
            pytest ${testPath} \\
                -v \\
                --alluredir=${args.reportDir} \\
                --tb=short \\
                --junit-xml=reports/junit-${args.env}.xml \\
                ${markerArg}
    """
}

// 企业微信通知函数
def sendWeChatNotification(Map args) {
    def webhook = env.WECHAT_WEBHOOK
    if (!webhook) {
        echo "WECHAT_WEBHOOK 未配置，跳过通知"
        return
    }

    def icon    = args.status == 'success' ? '✅' : '❌'
    def color   = args.status == 'success' ? 'info' : 'warning'
    def statusText = args.status == 'success' ? '**全部通过**' : '**存在失败**'
    def now     = new Date().format('yyyy-MM-dd HH:mm:ss')

    def content = """## ${icon} 自动化测试流水线完成

> **构建号**: #${args.buildNumber}
> **提交**: ${args.gitCommit}
> **模式**: ${args.pipelineType}
> **模块**: ${args.module}
> **环境**: ${args.env}
> **时间**: ${now}

### 结果：<font color="${color}">${statusText}</font>

[查看看板](${args.platformUrl}) | [查看报告](${args.allureUrl}/allure-docker-service/latest-report/index.html)"""

    def payload = groovy.json.JsonOutput.toJson([
        msgtype:  'markdown',
        markdown: [content: content]
    ])

    sh """
        curl -s -X POST '${webhook}' \\
            -H 'Content-Type: application/json' \\
            -d '${payload}' || true
    """
}