pipeline {
    agent any

    environment {
        IMAGE_NAME   = "auto-test-platform"
        IMAGE_TAG    = "${IMAGE_NAME}:${BUILD_NUMBER}"
        ALLURE_DIR   = "reports/allure-results"
        PLATFORM_URL = "http://your-server:5173"
        ALLURE_URL   = "http://your-server:5050"
    }

    parameters {
        choice(
            name: 'PIPELINE_TYPE',
            choices: ['single', 'multi-env', 'smoke-only'],
            description: 'single=单环境 | multi-env=多环境并行 | smoke-only=仅冒烟'
        )
        choice(name: 'MODULE',  choices: ['all', 'ui', 'api'], description: '测试模块')
        choice(name: 'ENV',     choices: ['dev', 'test', 'prod'], description: '目标环境')
        string(name: 'MARKERS', defaultValue: '', description: 'pytest 标签，如 smoke')
    }

    triggers {
        cron('0 2 * * *')
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_SHORT = sh(
                        script: 'git rev-parse --short HEAD',
                        returnStdout: true
                    ).trim()
                    echo "当前 Commit: ${env.GIT_SHORT}"
                }
            }
        }

        stage('Notify: Pipeline Start') {
            steps {
                script {
                    sendEmailNotification(
                        subject: "测试流水线已启动 | #${BUILD_NUMBER} | ${params.ENV.toUpperCase()}",
                        body:    buildStartEmailBody(
                            BUILD_NUMBER,
                            params.PIPELINE_TYPE,
                            params.MODULE,
                            params.ENV,
                            currentBuild.getBuildCauses()[0]?.shortDescription ?: 'manual',
                            env.GIT_SHORT
                        )
                    )
                }
            }
        }

        stage('Build Image') {
            steps {
                sh "docker build -t ${IMAGE_TAG} ."
            }
        }

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

        stage('Run Tests - Multi-Env') {
            when { expression { params.PIPELINE_TYPE == 'multi-env' } }
            parallel {
                stage('DEV - Smoke') {
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
                            archiveArtifacts artifacts: 'reports/allure-results-dev/**',
                                             allowEmptyArchive: true
                        }
                    }
                }
                stage('TEST - Full') {
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
                            archiveArtifacts artifacts: 'reports/allure-results-test/**',
                                             allowEmptyArchive: true
                        }
                    }
                }
            }
        }

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

        stage('Merge Reports') {
            when { expression { params.PIPELINE_TYPE == 'multi-env' } }
            steps {
                sh """
                    mkdir -p ${env.ALLURE_DIR}
                    cp -r reports/allure-results-dev/*  ${env.ALLURE_DIR}/ 2>/dev/null || true
                    cp -r reports/allure-results-test/* ${env.ALLURE_DIR}/ 2>/dev/null || true
                """
            }
        }

        stage('Generate Allure Report') {
            steps {
                allure([results: [[path: env.ALLURE_DIR]]])
            }
        }
    }

    post {
        success {
            script {
                def body = buildResultEmailBody(
                    BUILD_NUMBER, 'success',
                    params.PIPELINE_TYPE, params.MODULE, params.ENV,
                    env.GIT_SHORT, currentBuild.getDuration(),
                    env.PLATFORM_URL, env.ALLURE_URL, BUILD_URL
                )
                sendEmailNotification(
                    subject: "✅ 测试通过 | #${BUILD_NUMBER} | ${params.MODULE} | ${params.ENV.toUpperCase()}",
                    body:    body
                )
            }
        }

        failure {
            script {
                def body = buildResultEmailBody(
                    BUILD_NUMBER, 'failure',
                    params.PIPELINE_TYPE, params.MODULE, params.ENV,
                    env.GIT_SHORT, currentBuild.getDuration(),
                    env.PLATFORM_URL, env.ALLURE_URL, BUILD_URL
                )
                sendEmailNotification(
                    subject: "❌ 测试失败 | #${BUILD_NUMBER} | ${params.MODULE} | ${params.ENV.toUpperCase()}",
                    body:    body
                )
            }
        }

        always {
            junit allowEmptyResults: true, testResults: 'reports/junit*.xml'
            archiveArtifacts artifacts: 'screenshots/**,logs/**', allowEmptyArchive: true
            sh "docker rmi ${IMAGE_TAG} || true"
        }
    }
}

// 工具函数

def runTestsInDocker(Map args) {
    def testPath  = (args.module == 'all') ? 'tests/' : "tests/${args.module}"
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

def sendEmailNotification(Map args) {
    def recipients = env.TEAM_EMAIL ?: ''
    if (!recipients) {
        echo "TEAM_EMAIL未配置，跳过邮件通知"
        return
    }
    emailext(
        subject:  args.subject,
        body:     args.body,
        mimeType: 'text/html',
        to:       recipients
    )
}

def buildStartEmailBody(buildNum, pipelineType, module, environment, trigger, gitCommit) {
    def now = new Date().format('yyyy-MM-dd HH:mm:ss')
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;
             font-family:'Microsoft YaHei',Arial,sans-serif;">
  <div style="max-width:560px;margin:32px auto;background:#fff;
              border-radius:12px;overflow:hidden;
              box-shadow:0 2px 12px rgba(0,0,0,0.08);">
    <div style="background:#1890ff;padding:24px 32px;text-align:center;">
      <div style="color:#fff;font-size:20px;font-weight:700;">🚀 测试流水线已启动</div>
    </div>
    <div style="padding:28px 32px;">
      <table style="width:100%;font-size:14px;">
        <tr>
          <td style="color:#999;padding:8px 0;width:100px;">构建号</td>
          <td style="color:#333;font-weight:600;">#${buildNum}</td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">提交</td>
          <td style="color:#333;font-family:monospace;">${gitCommit}</td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">流水线类型</td>
          <td style="color:#333;">${pipelineType}</td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">测试模块</td>
          <td style="color:#333;">${module}</td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">测试环境</td>
          <td>
            <span style="background:#e6f7ff;color:#1890ff;padding:2px 10px;
                         border-radius:10px;font-size:12px;">
              ${environment.toUpperCase()}
            </span>
          </td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">触发方式</td>
          <td style="color:#333;">${trigger}</td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">启动时间</td>
          <td style="color:#333;">${now}</td>
        </tr>
      </table>
      <div style="margin-top:20px;padding:14px;background:#e6f7ff;
                  border-radius:8px;text-align:center;color:#1890ff;font-size:13px;">
        测试执行中，完成后将自动发送结果邮件...
      </div>
    </div>
    <div style="padding:16px 32px;background:#fafafa;border-top:1px solid #f0f0f0;
                text-align:center;">
      <p style="margin:0;color:#bfbfbf;font-size:12px;">此邮件由 Jenkins 自动发送，请勿回复</p>
    </div>
  </div>
</body>
</html>
    """
}

def buildResultEmailBody(buildNum, status, pipelineType, module, environment,
                         gitCommit, durationMs, platformUrl, allureUrl, buildUrl) {
    def isSuccess    = (status == 'success')
    def statusColor  = isSuccess ? '#27ae60' : '#e74c3c'
    def statusText   = isSuccess ? '✅ 构建成功' : '❌ 构建失败'
    def durationSecs = (durationMs / 1000).toLong()
    def now          = new Date().format('yyyy-MM-dd HH:mm:ss')

    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;
             font-family:'Microsoft YaHei',Arial,sans-serif;">
  <div style="max-width:600px;margin:32px auto;background:#fff;
              border-radius:12px;overflow:hidden;
              box-shadow:0 2px 12px rgba(0,0,0,0.08);">
    <div style="background:${statusColor};padding:28px 32px;text-align:center;">
      <div style="color:#fff;font-size:22px;font-weight:700;">${statusText}</div>
      <div style="color:rgba(255,255,255,0.85);font-size:13px;margin-top:6px;">
        构建 #${buildNum} · ${environment.toUpperCase()} 环境
      </div>
    </div>
    <div style="padding:28px 32px;">
      <table style="width:100%;font-size:14px;margin-bottom:24px;">
        <tr>
          <td style="color:#999;padding:8px 0;width:100px;">构建号</td>
          <td style="color:#333;font-weight:600;">#${buildNum}</td>
          <td style="color:#999;padding:8px 0;width:100px;">提交</td>
          <td style="color:#333;font-family:monospace;">${gitCommit}</td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">流水线类型</td>
          <td style="color:#333;">${pipelineType}</td>
          <td style="color:#999;padding:8px 0;">测试模块</td>
          <td style="color:#333;">${module}</td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">执行耗时</td>
          <td style="color:#333;">${durationSecs} 秒</td>
          <td style="color:#999;padding:8px 0;">完成时间</td>
          <td style="color:#333;">${now}</td>
        </tr>
      </table>
      <div style="text-align:center;margin-top:24px;">
        <a href="${platformUrl}" style="display:inline-block;margin-right:12px;
           padding:10px 24px;background:#1890ff;color:#fff;text-decoration:none;
           border-radius:6px;font-size:14px;">
           查看测试看板
        </a>
        <a href="${allureUrl}" style="display:inline-block;margin-right:12px;
           padding:10px 24px;background:#13c2c2;color:#fff;text-decoration:none;
           border-radius:6px;font-size:14px;">
           Allure报告
        </a>
        <a href="${buildUrl}" style="display:inline-block;padding:10px 24px;
           background:#722ed1;color:#fff;text-decoration:none;
           border-radius:6px;font-size:14px;">
           Jenkins详情
        </a>
      </div>
    </div>
    <div style="padding:16px 32px;background:#fafafa;border-top:1px solid #f0f0f0;
                text-align:center;">
      <p style="margin:0;color:#bfbfbf;font-size:12px;">
        此邮件由 Jenkins + 自动化测试平台自动发送，请勿回复
      </p>
    </div>
  </div>
</body>
</html>
    """
}