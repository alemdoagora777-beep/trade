# Estágio de compilação (Build Stage)
FROM node:20-slim AS builder

WORKDIR /app

# Copia arquivos de configuração das dependências
COPY package*.json ./

# Instala todas as dependências (essencial incluir as devDependencies para compilação como esbuild e vite)
RUN npm ci

# Copia os arquivos de código-fonte
COPY . .

# Executa o script de compilação (gera a pasta dist/ e compila o server.cjs)
RUN npm run build

# Estágio de execução (Production Runtime Stage)
FROM node:20-slim AS runner

WORKDIR /app

# Configura as variáveis de ambiente necessárias
ENV NODE_ENV=production
ENV PORT=3000

# Copia os arquivos compilados e manifests do estágio anterior
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/dist ./dist

# Instala apenas as dependências de produção para manter a imagem limpa e leve
RUN npm ci --omit=dev

# Expõe a porta designada (Railway mapeia para process.env.PORT automaticamente)
EXPOSE 3000

# Inicia o servidor Node compilado
CMD ["npm", "start"]
