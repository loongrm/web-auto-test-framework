"""
邮件通知服务
支持：QQ邮箱 / 163邮箱 / Gmail / 企业邮箱（SMTP）
"""
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from core.log_factory import log


import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.header import Header
from email.utils import formataddr
from email import encoders
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from core.log_factory import log


class EmailService:

    def __init__(self):
        self.smtp_host     = os.getenv("SMTP_HOST", "smtp.qq.com")
        self.smtp_port     = int(os.getenv("SMTP_PORT", "465"))
        self.smtp_user     = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_use_ssl  = os.getenv("SMTP_USE_SSL", "true").lower() == "true"
        self.sender_name   = os.getenv("SMTP_SENDER_NAME", "自动化测试平台")
        self.enabled       = bool(self.smtp_user and self.smtp_password)

        if not self.enabled:
            log.warning("SMTP_USER / SMTP_PASSWORD 未配置，邮件通知不可用")

    # 核心发送方法

    def send(
        self,
        to: List[str],
        subject: str,
        html_body: str,
        attachments: List[str] = None,
        cc: List[str] = None,
    ) -> bool:
        if not self.enabled:
            log.warning("邮件服务未配置，跳过发送")
            return False

        try:
            msg = MIMEMultipart("alternative")

            # 用formataddr + Header正确编码中文发件人
            msg["Subject"] = Header(subject, "utf-8").encode()
            msg["From"]    = formataddr(
                (Header(self.sender_name, "utf-8").encode(), self.smtp_user)
            )
            msg["To"]      = ", ".join(to)
            if cc:
                msg["Cc"] = ", ".join(cc)

            # HTML 正文
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            # 附件
            for path in (attachments or []):
                p = Path(path)
                if not p.exists():
                    log.warning(f"附件不存在，跳过: {path}")
                    continue
                with open(p, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{p.name}"',
                )
                msg.attach(part)

            all_recipients = to + (cc or [])

            if self.smtp_use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_user, all_recipients, msg.as_string())
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_user, all_recipients, msg.as_string())

            log.info(f"邮件已发送 | 收件人: {to} | 主题: {subject}")
            return True

        except smtplib.SMTPAuthenticationError:
            log.error("SMTP 认证失败，请检查授权码是否正确（QQ邮箱填授权码不是登录密码）")
            return False
        except smtplib.SMTPConnectError:
            log.error(f"SMTP 连接失败，请检查 HOST={self.smtp_host} PORT={self.smtp_port}")
            return False
        except Exception as e:
            log.error(f"邮件发送异常: {e}")
            return False

    # 业务邮件模板

    def send_test_result(
        self,
        to: List[str],
        run_id: int,
        module: str,
        env: str,
        status: str,
        total: int,
        passed: int,
        failed: int,
        skipped: int,
        duration: float,
        trigger: str = "manual",
        dashboard_url: str = "",
        allure_url: str = "",
        failed_cases: List[dict] = None,
        ai_summary: str = "",
    ) -> bool:
        """测试执行结果通知邮件"""
        pass_rate    = round(passed / total * 100, 1) if total else 0
        is_success   = status == "success"
        status_color = "#27ae60" if is_success else "#e74c3c"
        status_text  = "✅全部通过" if is_success else "❌存在失败用例"
        now          = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject      = f"{'✅' if is_success else '❌'} 自动化测试报告 | {module} | {env} | #{run_id}"

        # 失败用例列表 HTML
        failed_table = ""
        if failed_cases:
            rows = "".join(
                f"""
                <tr>
                    <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#555;">
                        {i + 1}
                    </td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;
                               font-family:monospace;font-size:12px;color:#333;word-break:break-all;">
                        {case.get("name", "")}
                    </td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;
                               color:#e74c3c;font-size:12px;word-break:break-all;">
                        {(case.get("error_message") or "")[:120]}
                    </td>
                </tr>
                """
                for i, case in enumerate(failed_cases[:15])
            )
            extra = (
                f'<tr><td colspan="3" style="padding:8px 12px;color:#999;text-align:center;">'
                f'... 共 {len(failed_cases)} 条失败用例，仅展示前15条</td></tr>'
                if len(failed_cases) > 15 else ""
            )
            failed_table = f"""
            <div style="margin-top:32px;">
                <h2 style="color:#e74c3c;font-size:16px;margin-bottom:12px;
                           border-left:4px solid #e74c3c;padding-left:10px;">
                    失败用例详情
                </h2>
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead>
                        <tr style="background:#fff5f5;">
                            <th style="padding:10px 12px;text-align:left;color:#e74c3c;
                                       width:40px;">#</th>
                            <th style="padding:10px 12px;text-align:left;color:#e74c3c;">用例名称</th>
                            <th style="padding:10px 12px;text-align:left;color:#e74c3c;">错误摘要</th>
                        </tr>
                    </thead>
                    <tbody>{rows}{extra}</tbody>
                </table>
            </div>
            """

        # AI摘要HTML
        ai_section = ""
        if ai_summary:
            ai_section = f"""
            <div style="margin-top:32px;padding:20px;background:#f8f0ff;
                        border-radius:8px;border-left:4px solid #9b59b6;">
                <h2 style="color:#9b59b6;font-size:16px;margin:0 0 12px;">
                    AI智能摘要
                </h2>
                <p style="color:#555;line-height:1.8;margin:0;font-size:14px;">
                    {ai_summary}
                </p>
            </div>
            """

        # 操作按钮
        buttons = ""
        if dashboard_url:
            buttons += f"""
            <a href="{dashboard_url}" style="display:inline-block;margin-right:12px;
               padding:10px 24px;background:#1890ff;color:#fff;text-decoration:none;
               border-radius:6px;font-size:14px;font-weight:500;">
               查看看板
            </a>
            """
        if allure_url:
            buttons += f"""
            <a href="{allure_url}" style="display:inline-block;padding:10px 24px;
               background:#13c2c2;color:#fff;text-decoration:none;
               border-radius:6px;font-size:14px;font-weight:500;">
               查看Allure报告
            </a>
            """

        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:'PingFang SC','Microsoft YaHei',
             'Helvetica Neue',Arial,sans-serif;">
  <div style="max-width:680px;margin:32px auto;background:#fff;
              border-radius:12px;overflow:hidden;
              box-shadow:0 2px 12px rgba(0,0,0,0.08);">

    <!-- 顶部状态栏 -->
    <div style="background:{status_color};padding:28px 32px;text-align:center;">
      <div style="color:#fff;font-size:24px;font-weight:700;letter-spacing:0.5px;">
        {status_text}
      </div>
      <div style="color:rgba(255,255,255,0.85);font-size:14px;margin-top:6px;">
        自动化测试平台 · Run #{run_id}
      </div>
    </div>

    <!-- 主体内容 -->
    <div style="padding:32px;">

      <!-- 执行信息 -->
      <table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
        <tr>
          <td style="padding:6px 0;color:#999;font-size:13px;width:100px;">测试模块</td>
          <td style="padding:6px 0;color:#333;font-size:13px;font-weight:500;">{module}</td>
          <td style="padding:6px 0;color:#999;font-size:13px;width:100px;">测试环境</td>
          <td style="padding:6px 0;">
            <span style="background:#e6f7ff;color:#1890ff;padding:2px 10px;
                         border-radius:10px;font-size:12px;">{env.upper()}</span>
          </td>
        </tr>
        <tr>
          <td style="padding:6px 0;color:#999;font-size:13px;">触发方式</td>
          <td style="padding:6px 0;color:#333;font-size:13px;">{trigger}</td>
          <td style="padding:6px 0;color:#999;font-size:13px;">执行时间</td>
          <td style="padding:6px 0;color:#333;font-size:13px;">{now}</td>
        </tr>
        <tr>
          <td style="padding:6px 0;color:#999;font-size:13px;">执行耗时</td>
          <td style="padding:6px 0;color:#333;font-size:13px;">{duration:.1f} 秒</td>
          <td style="padding:6px 0;color:#999;font-size:13px;">Run ID</td>
          <td style="padding:6px 0;color:#333;font-size:13px;">#{run_id}</td>
        </tr>
      </table>

      <!-- 统计数据卡片 -->
      <div style="display:flex;gap:12px;margin-bottom:24px;">
        <div style="flex:1;text-align:center;padding:20px 12px;background:#f6ffed;
                    border-radius:8px;border:1px solid #b7eb8f;">
          <div style="font-size:28px;font-weight:700;color:#52c41a;">{pass_rate}%</div>
          <div style="font-size:12px;color:#73d13d;margin-top:4px;">通过率</div>
        </div>
        <div style="flex:1;text-align:center;padding:20px 12px;background:#f6ffed;
                    border-radius:8px;border:1px solid #b7eb8f;">
          <div style="font-size:28px;font-weight:700;color:#52c41a;">{passed}</div>
          <div style="font-size:12px;color:#73d13d;margin-top:4px;">通过</div>
        </div>
        <div style="flex:1;text-align:center;padding:20px 12px;
                    background:{'#fff2f0' if failed else '#fafafa'};
                    border-radius:8px;
                    border:1px solid {'#ffccc7' if failed else '#d9d9d9'};">
          <div style="font-size:28px;font-weight:700;
                      color:{'#f5222d' if failed else '#bfbfbf'};">{failed}</div>
          <div style="font-size:12px;color:{'#ff7875' if failed else '#bfbfbf'};
                      margin-top:4px;">失败</div>
        </div>
        <div style="flex:1;text-align:center;padding:20px 12px;background:#fafafa;
                    border-radius:8px;border:1px solid #d9d9d9;">
          <div style="font-size:28px;font-weight:700;color:#bfbfbf;">{skipped}</div>
          <div style="font-size:12px;color:#bfbfbf;margin-top:4px;">跳过</div>
        </div>
        <div style="flex:1;text-align:center;padding:20px 12px;background:#f0f5ff;
                    border-radius:8px;border:1px solid #adc6ff;">
          <div style="font-size:28px;font-weight:700;color:#2f54eb;">{total}</div>
          <div style="font-size:12px;color:#597ef7;margin-top:4px;">总计</div>
        </div>
      </div>

      <!-- AI 摘要 -->
      {ai_section}

      <!-- 失败用例表 -->
      {failed_table}

      <!-- 操作按钮 -->
      {f'<div style="margin-top:32px;text-align:center;">{buttons}</div>' if buttons else ''}

    </div>

    <!-- 底部 -->
    <div style="padding:20px 32px;background:#fafafa;border-top:1px solid #f0f0f0;
                text-align:center;">
      <p style="margin:0;color:#bfbfbf;font-size:12px;">
        此邮件由自动化测试平台自动发送，请勿直接回复
      </p>
      <p style="margin:6px 0 0;color:#bfbfbf;font-size:12px;">
        {now} · {env.upper()} 环境
      </p>
    </div>

  </div>
</body>
</html>
        """
        return self.send(to=to, subject=subject, html_body=html)

    def send_failure_alert(
        self,
        to: List[str],
        case_name: str,
        error_log: str,
        screenshot_path: str = "",
        ai_analysis: dict = None,
    ) -> bool:
        """单条用例失败告警邮件（适合实时触发）"""
        now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = f"用例失败警告 | {case_name[:50]}"

        ai_section = ""
        if ai_analysis and ai_analysis.get("available"):
            type_map = {
                "element_not_found": "元素未找到",
                "timeout":           "超时",
                "assertion_error":   "断言失败",
                "network_error":     "网络错误",
                "environment_issue": "环境问题",
                "application_bug":   "应用 Bug",
                "test_data_issue":   "测试数据问题",
            }
            ftype = type_map.get(ai_analysis.get("failure_type", ""), ai_analysis.get("failure_type", ""))
            ai_section = f"""
            <div style="margin-top:24px;padding:16px;background:#f8f0ff;
                        border-radius:8px;border-left:4px solid #9b59b6;">
              <div style="font-size:14px;font-weight:600;color:#9b59b6;margin-bottom:10px;">
                AI分析结果
              </div>
              <table style="width:100%;font-size:13px;">
                <tr>
                  <td style="color:#999;padding:4px 0;width:80px;">失败类型</td>
                  <td style="color:#333;padding:4px 0;">{ftype}</td>
                </tr>
                <tr>
                  <td style="color:#999;padding:4px 0;">根本原因</td>
                  <td style="color:#333;padding:4px 0;">{ai_analysis.get("root_cause", "")}</td>
                </tr>
                <tr>
                  <td style="color:#999;padding:4px 0;">修复建议</td>
                  <td style="color:#333;padding:4px 0;line-height:1.6;">
                    {ai_analysis.get("suggestion", "")}
                  </td>
                </tr>
                <tr>
                  <td style="color:#999;padding:4px 0;">置信度</td>
                  <td style="color:#333;padding:4px 0;">
                    {int(ai_analysis.get("confidence", 0) * 100)}%
                  </td>
                </tr>
                <tr>
                  <td style="color:#999;padding:4px 0;">是否 Flaky</td>
                  <td style="color:#333;padding:4px 0;">
                    {"是 — " + ai_analysis.get("flaky_reason", "") if ai_analysis.get("is_flaky") else "否"}
                  </td>
                </tr>
              </table>
            </div>
            """

        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;
             font-family:'PingFang SC','Microsoft YaHei',Arial,sans-serif;">
  <div style="max-width:680px;margin:32px auto;background:#fff;
              border-radius:12px;overflow:hidden;
              box-shadow:0 2px 12px rgba(0,0,0,0.08);">

    <div style="background:#e74c3c;padding:24px 32px;">
      <div style="color:#fff;font-size:20px;font-weight:700;">用例失败警告</div>
      <div style="color:rgba(255,255,255,0.85);font-size:13px;margin-top:6px;">
        {now}
      </div>
    </div>

    <div style="padding:28px 32px;">
      <div style="padding:14px 16px;background:#fff2f0;border-radius:8px;
                  border:1px solid #ffccc7;margin-bottom:20px;">
        <div style="font-size:12px;color:#ff7875;margin-bottom:4px;">失败用例</div>
        <div style="font-family:monospace;font-size:14px;color:#cf1322;word-break:break-all;">
          {case_name}
        </div>
      </div>

      <div style="margin-bottom:20px;">
        <div style="font-size:13px;font-weight:600;color:#555;margin-bottom:8px;">错误日志</div>
        <pre style="background:#1a1a1a;color:#ff6b6b;padding:16px;border-radius:8px;
                    font-size:12px;line-height:1.6;overflow-x:auto;white-space:pre-wrap;
                    word-break:break-all;margin:0;">{error_log[:2000]}</pre>
      </div>

      {ai_section}
    </div>

    <div style="padding:16px 32px;background:#fafafa;border-top:1px solid #f0f0f0;
                text-align:center;">
      <p style="margin:0;color:#bfbfbf;font-size:12px;">
        此邮件由自动化测试平台自动发送，请勿直接回复
      </p>
    </div>
  </div>
</body>
</html>
        """
        attachments = [screenshot_path] if screenshot_path and Path(screenshot_path).exists() else []
        return self.send(to=to, subject=subject, html_body=html, attachments=attachments)

    def send_pipeline_start(
        self,
        to: List[str],
        build_number: int,
        module: str,
        env: str,
        trigger: str,
        pipeline_type: str,
    ) -> bool:
        """流水线开始通知"""
        now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = f"测试流水线已启动 | #{build_number} | {env.upper()}"
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;
             font-family:'PingFang SC','Microsoft YaHei',Arial,sans-serif;">
  <div style="max-width:560px;margin:32px auto;background:#fff;
              border-radius:12px;overflow:hidden;
              box-shadow:0 2px 12px rgba(0,0,0,0.08);">
    <div style="background:#1890ff;padding:24px 32px;text-align:center;">
      <div style="color:#fff;font-size:20px;font-weight:700;">测试流水线已启动</div>
    </div>
    <div style="padding:28px 32px;">
      <table style="width:100%;font-size:14px;">
        <tr>
          <td style="color:#999;padding:8px 0;width:100px;">构建号</td>
          <td style="color:#333;font-weight:600;">#{build_number}</td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">流水线类型</td>
          <td style="color:#333;">{pipeline_type}</td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">测试模块</td>
          <td style="color:#333;">{module}</td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">测试环境</td>
          <td>
            <span style="background:#e6f7ff;color:#1890ff;padding:2px 10px;
                         border-radius:10px;font-size:12px;">{env.upper()}</span>
          </td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">触发方式</td>
          <td style="color:#333;">{trigger}</td>
        </tr>
        <tr>
          <td style="color:#999;padding:8px 0;">启动时间</td>
          <td style="color:#333;">{now}</td>
        </tr>
      </table>
      <div style="margin-top:20px;padding:14px;background:#e6f7ff;border-radius:8px;
                  text-align:center;color:#1890ff;font-size:13px;">
        测试执行中，完成后将自动发送结果通知...
      </div>
    </div>
  </div>
</body>
</html>
        """
        return self.send(to=to, subject=subject, html_body=html)

    def send_test(self, to: List[str]) -> bool:
        """发送测试连通性邮件，用于验证配置是否正确"""
        now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = "自动化测试平台 | 邮件配置验证成功"
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;
             font-family:'PingFang SC','Microsoft YaHei',Arial,sans-serif;">
  <div style="max-width:480px;margin:60px auto;background:#fff;
              border-radius:12px;overflow:hidden;
              box-shadow:0 2px 12px rgba(0,0,0,0.08);text-align:center;">
    <div style="background:#27ae60;padding:32px;">
      <div style="font-size:48px;">✅</div>
      <div style="color:#fff;font-size:20px;font-weight:700;margin-top:12px;">
        邮件配置验证成功
      </div>
    </div>
    <div style="padding:32px;">
      <p style="color:#555;font-size:14px;line-height:1.8;">
        自动化测试平台的邮件通知服务已成功配置。<br>
        后续测试执行结果将自动发送到此邮箱。
      </p>
      <p style="color:#999;font-size:12px;margin-top:24px;">
        发送时间：{now}
      </p>
    </div>
  </div>
</body>
</html>
        """
        return self.send(to=to, subject=subject, html_body=html)


# 全局单例
email_service = EmailService()