FROM python:3.12-slim

# 系统依赖（Playwright Chromium 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    nodejs npm \
    && npm install -g newman newman-reporter-htmlextra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/

# 安装 Playwright 浏览器
RUN playwright install chromium && playwright install-deps chromium

COPY . .

ENV TEST_ENV=test
ENV PYTHONPATH=/app

CMD ["pytest", "tests/", "-v", "--alluredir=reports/allure-results", "--tb=short"]