# 前端镜像：Vue3 + Vite 多阶段构建（node 构建 -> nginx 托管）
# 构建上下文：frontend/ 目录
#   docker build -t scholarship-frontend ./frontend
FROM node:20-alpine AS build

WORKDIR /app

# 优先用 lockfile 精确安装；无 lockfile 时退回 npm install（国内使用 npmmirror 源）
COPY package.json package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com \
    && (npm ci --no-audit --no-fund || npm install --no-audit --no-fund)

COPY . .
RUN npm run build

# ---------- 运行阶段 ----------
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
