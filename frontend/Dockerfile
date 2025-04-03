# Використовуємо базовий образ Node.js для побудови фронтенду
FROM node:20 AS builder

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо package.json та package-lock.json (якщо є)
COPY package.json .
COPY package-lock.json .

# Копіюємо .env файл для Vite (важливо для збірки!)
COPY .env .

# Встановлюємо залежності
RUN npm install

# Копіюємо весь код
COPY . .

# Створюємо продакшн-версію додатка
RUN npm run build

# Використовуємо Nginx для хостингу статичних файлів
FROM nginx:alpine

# Копіюємо збудовані файли з попереднього етапу
COPY --from=builder /app/dist /usr/share/nginx/html


# Відкриваємо порт 80 (Nginx працює на 80 за замовчуванням)
EXPOSE 80

# Запускаємо Nginx, щоб віддавати React додаток
CMD ["nginx", "-g", "daemon off;"]