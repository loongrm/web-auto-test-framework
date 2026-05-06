import os
from typing import Optional
from core.log_factory import log


class JenkinsService:
    """
    Jenkins 集成服务
    若未配置 Jenkins 环境变量，所有方法静默跳过
    """

    def __init__(self):
        self._server = None
        self._available = False
        self._init()

    def _init(self):
        url = os.getenv("JENKINS_URL")
        user = os.getenv("JENKINS_USER")
        token = os.getenv("JENKINS_TOKEN")
        if not all([url, user, token]):
            log.warning("Jenkins 未配置，相关功能不可用")
            return
        try:
            import jenkins
            self._server = jenkins.Jenkins(url, username=user, password=token)
            self._server.get_whoami()
            self._available = True
            log.info(f"Jenkins 连接成功: {url}")
        except Exception as e:
            log.error(f"Jenkins 连接失败: {e}")

    @property
    def available(self) -> bool:
        return self._available

    def trigger_job(self, job_name: str, params: dict = None) -> Optional[int]:
        """触发 Jenkins 任务，返回队列 ID"""
        if not self._available:
            return None
        try:
            queue_id = self._server.build_job(job_name, parameters=params or {})
            log.info(f"Jenkins 任务已触发: {job_name} | 队列ID: {queue_id}")
            return queue_id
        except Exception as e:
            log.error(f"触发 Jenkins 任务失败: {e}")
            return None

    def get_last_build_info(self, job_name: str) -> Optional[dict]:
        if not self._available:
            return None
        try:
            return self._server.get_last_build_info(job_name)
        except Exception as e:
            log.error(f"获取 Jenkins 构建信息失败: {e}")
            return None

    def get_job_list(self) -> list:
        if not self._available:
            return []
        try:
            return [j["name"] for j in self._server.get_jobs()]
        except Exception:
            return []