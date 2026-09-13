FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Vite inlines env at build time, so the API URL is a build arg rather than a
# runtime variable. It must be reachable from the browser, not from the network
# inside compose, so it is localhost rather than the service name.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# Hosts like Railway assign a port through PORT. The official nginx entrypoint
# renders anything in templates/ with envsubst before starting, so the port
# stays configurable without a custom entrypoint. The template deliberately
# avoids nginx variables such as $uri, which envsubst would blank out.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV PORT=80
EXPOSE 80
