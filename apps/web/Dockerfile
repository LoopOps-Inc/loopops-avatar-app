FROM node:22-alpine AS build
WORKDIR /repo
COPY package.json package-lock.json .npmrc ./
COPY apps/web/package.json apps/web/package.json
COPY apps/native/package.json apps/native/package.json
COPY packages/contracts/package.json packages/contracts/package.json
COPY packages/eslint-config-native/package.json packages/eslint-config-native/package.json
RUN npm ci --no-audit --no-fund --ignore-scripts
COPY packages/contracts packages/contracts
COPY apps/web apps/web
RUN npm run build -w apps/web

FROM nginx:1.27-alpine
COPY --from=build /repo/apps/web/dist /usr/share/nginx/html
COPY apps/web/nginx/ /etc/nginx/templates/
COPY apps/web/docker-entrypoint.sh /docker-entrypoint.d/15-read-token.envsh
EXPOSE 8080
