# Stage 1: Build the React Application
FROM node:20-alpine AS build

WORKDIR /app

# Accept the build argument
ARG VITE_API_URL
# Set it as an environment variable for the build process
ENV VITE_API_URL=$VITE_API_URL

# Copy package files and install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy the rest of the application code
COPY . .

# Build the app
RUN npm run build

# Stage 2: Serve the App with Nginx
FROM nginx:alpine

# Copy the built assets from the previous stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]