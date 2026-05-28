# -*- coding: utf-8 -*-
"""
🏆 ENGENHARIA DE ANÁLISES ESPECIAIS (MOTOR C - EXTREMOS DE MERCADO)
SISTEMA: HONRANDO E PROSPERANDO PARA A GLÓRIA DE DEUS
----------------------------------------------------------------------
Este robô de varredura especializada monitora o mercado futuro da Binance,
procurando por desvios extremos de preço (pânico/crashes ou euforia do tipo pump),
filtrados por desvios estatísticos de Bollinger, volume anormal (RVOL) e confirmados
por multi-timeframe (MTF) de tempos gráficos maiores para capturar reversões cirúrgicas.

Versículo de Fé:
"Confia as tuas obras ao Senhor, e os teus pensamentos serão estabelecidos." (Provérbios 16:3)
"""

import os
import sys
import time
import requests
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

# ==============================================================================
# CONFIGURAÇÕES GERAIS E INTEGRAÇÃO (ATUALIZE DE ACORDO COM SEU AMBIENTE)
# ==============================================================================
# URL DO SISTEMA WEB DA SUA PLATAFORMA (Importante para enviar sinais ao Motor C)
WEBHOOK_URL = "https://ais-pre-v7fmlssn3oehfn7sypgbtc-335113295610.us-west1.run.app/webhook"

# Seus Tokens e IDs do Telegram para Alertas (Armado e Executado)
TG_TOKEN_ARMADO = "8667082024:AAEMyrCuVMwHHpoAP56CDeDOCUNmsa-IJ5E"
TG_TOKEN_EXECUTADO = "8888159023:AAHj5nAXI8zoBcWbK1ZTr8Y10kqdeND0354"
TG_CHAT_ID = "7216099531"

# Moedas prioritárias de Alta Liquidez para Varredura Especializada (Caso dinâmico desativado)
MOEDAS_ALVO_FIXO = ["SOL", "BTC", "ETH", "BNB", "AVAX", "LINK", "ADA", "DOGE", "NEAR", "XRP"]

# Configuração de Escaneamento Dinâmico por Volume com Ultra Proteção de IP
USAR_LISTA_DINAMICA = True        # Se True, escaneia dinamicamente as moedas de MAIOR volume de 24h
LIMITE_MOEDAS_DINAMICAS = 240     # Varre as 240 moedas de maior volume (Liquidez extrema no mercado)
CACHE_MOEDAS_MINUTOS = 60         # Recarrega a lista de moedas por volume a cada 60 minutos (evita requisições pesadas à Binance)

# ==============================================================================
# PARÂMETROS MATEMÁTICOS DE ANÁLISE ULTRA-EXTREMA
# ==============================================================================
TF_CURTO = "5m"      # Tempo de execução (captura de pavios e espasmos de pânico/euforia)
TF_MACRO = "1h"      # Tempo macro confirmatório (evita "pegar facas caindo" em contra-tendência forte)

# Filtros do Tempo Curto (5m)
RSI_EXTREMO_OVERSOLD = 22.0     # Pânico Extremo (Abaixo de 22) - Gatilho de LONG
RSI_EXTREMO_OVERBOUGHT = 78.0   # Exaustão Compradora (Acima de 78) - Gatilho de SHORT
BOLLINGER_DESVIO = 2.5          # Quantos desvios padrão o preço deve sair da banda (Recomendado: 2.5 ou 3.0)
RVOL_MINIMO = 2.0               # O volume do candle atual deve ser no mínimo 2x maior que a média de 20 candles

# ==============================================================================
# ESTADO GLOBAL DO DASHBOARD TERMINAL
# ==============================================================================
state_dashboard = {
    "status": "INICIALIZANDO",
    "total_moedas": 0,
    "moeda_atual": "",
    "progresso_index": 0,
    "erros_conexao": 0,
    "limites_atingidos": 0,
    "rate_limits": 0,
    "ddos_protections": 0,
    "historico_sinais": [],            # Sinais faturados com persistência de execução
    "ultimos_alertas": [],             # Avisos/Candidatos próximos do gatilho
    "ciclo_atual": 1,
    "tempo_inicio": time.time(),
    "ultimo_erro": ""
}

# ==============================================================================
# API BINANCE (CCXT)
# ==============================================================================
exchange = ccxt.binance({
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': True
    },
    'enableRateLimit': True,
    'timeout': 15000
})

# ==============================================================================
# FUNÇÃO DE DESENHO DO DASHBOARD INTERATIVO (ANSI TERMINAL UI)
# ==============================================================================
def desenhar_painel(moeda_sendo_varrida=None, progresso=0, total=0, extra_log=None):
    # Limpa a tela de forma profissional de acordo com o Sistema Operacional
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Paleta de Cores ANSI estruturada (Compatível com Windows CMD, VSCode e Terminais Unix)
    GOLD = "\033[38;2;251;191;36m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GRAY = "\033[90m"
    WHITE = "\033[97m"
    
    # Cabeçalho de Engenharia
    print(f"{GOLD}{BOLD}╔══════════════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{GOLD}{BOLD}║          🏆 ROBÔ EXTREMOS QUANT - MOTOR C (VARREDURA ULTRA-LIQUIDEZ)         ║{RESET}")
    print(f"{GOLD}{BOLD}║                - \"Consagre ao Senhor tudo o que você faz\" -                  ║{RESET}")
    print(f"{GOLD}{BOLD}╚══════════════════════════════════════════════════════════════════════════════╝{RESET}")
    
    # Calcular Tempo ativo (Uptime)
    segundos_ativos = int(time.time() - state_dashboard["tempo_inicio"])
    minutos_ativos = segundos_ativos // 60
    if minutos_ativos < 60:
        uptime_str = f"{minutos_ativos}m"
    else:
        hrs = minutos_ativos // 60
        uptime_str = f"{hrs}h {minutos_ativos % 60}m"
        
    status_formatado = f"{GREEN}ATULUZANDO PATRULHA{RESET}"
    if moeda_sendo_varrida is None:
        status_formatado = f"{GOLD}RESPIRANDO (45s DELAY){RESET}"
    if state_dashboard["status"] == "RATE_LIMIT_DELAY":
        status_formatado = f"{RED}BLOQUEIO IP: PAUSA SENSÍVEL{RESET}"
        
    # Painel de Status de Rede e API
    req_lim_str = f"{state_dashboard['rate_limits']} limites / {state_dashboard['ddos_protections']} DDoS"
    print(f" {BOLD}Uptime do Sistema:{RESET} {WHITE}{uptime_str}{RESET}      │  {BOLD}Status Operador:{RESET} {status_formatado}")
    print(f" {BOLD}Moedas em Patrulha:{RESET} {CYAN}{state_dashboard['total_moedas']} ativos{RESET} │  {BOLD}Sinais com Webhook OK:{RESET} {GOLD}{len(state_dashboard['historico_sinais'])}{RESET}")
    print(f" {BOLD}Escala de Varredura:{RESET} {WHITE}{TF_CURTO} Curto + {TF_MACRO} Macro{RESET}  │  {BOLD}Banda Desvios:{RESET} {WHITE}{BOLLINGER_DESVIO}σ{RESET}")
    print(f" {BOLD}Gatilhos Extremos:{RESET} {RED}RSI < {RSI_EXTREMO_OVERSOLD} / > {RSI_EXTREMO_OVERBOUGHT}{RESET} e {GOLD}RVOL > {RVOL_MINIMO}x{RESET}")
    print(f" {BOLD}Proteção de IP:{RESET} {WHITE}{req_lim_str}{RESET}           │  {BOLD}Ciclo de Varredura:{RESET} #{state_dashboard['ciclo_atual']}")
    print(f"{GRAY}───────────────────────────────────────────────────────────────────────────────{RESET}")
    
    # Barra de Progresso Real-Time
    if total > 0:
        pct = (progresso / total) * 100
        filled_size = int(30 * progresso // total)
        bar = '█' * filled_size + '░' * (30 - filled_size)
        print(f" {BOLD}Progresso desta Varredura:{RESET} [{GREEN}{bar}{RESET}] {BOLD}{pct:.1f}%{RESET} ({progresso}/{total})")
        if moeda_sendo_varrida:
            print(f" 📡 {BOLD}Escaneando agora:{RESET} {CYAN}{moeda_sendo_varrida}USDT{RESET} | {GRAY}Calculando RSI, BBands, ADX e Volume...{RESET}")
        else:
            print(f" ☕ {BOLD}Status de Ciclo:{RESET} {GOLD}Varredura de {total} moedas concluída! Próxima rodada em breve...{RESET}")
    else:
        print(f" 🔍 {BOLD}Preparando motor:{RESET} {GOLD}Buscando lista prioritária de volumes de 24h Binance...{RESET}")
        
    print(f"{GRAY}───────────────────────────────────────────────────────────────────────────────{RESET}")
    
    # Tabela com as Últimas Ações e Sinais Emitidos (O motor web atualiza a ABA INICIO com esses dados!)
    print(f" {GOLD}{BOLD}📦 TABELA DE GATILHOS EXECUTADOS E ENVIADOS À PLATAFORMA (WEBHOOKS){RESET}")
    print(f"{GRAY} ┌───────────┬─────────┬─────────┬────────────┬─────────┬─────────┬──────────────┐{RESET}")
    print(f" {BOLD}│ HORÁRIO   │ ATIVO   │ DIREÇÃO │ PREÇO ENTR │ PSI (5M)│ VOL MULT│ ENVIO STATUS │{RESET}")
    print(f"{GRAY} ├───────────┼─────────┼─────────┼────────────┼─────────┼─────────┼──────────────┤{RESET}")
    
    historico_limitado = state_dashboard["historico_sinais"][-6:] # Mostra os últimos 6 sinais
    if not historico_limitado:
        print(f" │ {GRAY}Nenhum sinal emitido no ciclo atual. Buscando variações matemáticas...      {RESET}│")
    else:
        for s in reversed(historico_limitado):
            direcao_str = s["lado"]
            dir_color = GREEN if direcao_str == "LONG" else RED
            p_formatted = f"${s['preco']:.4f}" if s['preco'] < 1.0 else f"${s['preco']:.2f}"
            print(f" │ {s['hora']:<9} │ {s['moeda']:<7} │ {dir_color}{direcao_str:<7}{RESET} │ {p_formatted:<10} │ {s['rsi']:<7.1f} │ {s['rvol']:<7.1f}x │ {GREEN}SUCESSO WEB ✓{RESET} │")
            
    print(f"{GRAY} └───────────┴─────────┴─────────┴────────────┴─────────┴─────────┴──────────────┘{RESET}")
    
    # Alertas Rápidos de Ativos que rasgaram mas foram descartados ou filtrados por tendência
    alertas_ativos = state_dashboard["ultimos_alertas"][-3:]
    if alertas_ativos:
        print(f"\n {MAGENTA}{BOLD}⚡ RADAR DE ATIVOS EM LIMITE EXTREMO (FILTRADOS OU EM TESTE):{RESET}")
        for alt in reversed(alertas_ativos):
            p_str = f"${alt['preco']:.4f}" if alt['preco'] < 1.0 else f"${alt['preco']:.2f}"
            print(f"  • {GRAY}[{alt['hora']}]{RESET} {CYAN}{alt['moeda']}{RESET} - RSI: {alt['rsi']:.1f} | RVOL: {alt['rvol']:.1f}x | {alt['motivo']}")
            
    if extra_log:
        print(f"\n {BOLD}Histórico de logs:{RESET} {EXTRA_LOG_COLOR(extra_log)}{extra_log}{RESET}")
    elif state_dashboard["ultimo_erro"]:
        print(f"\n {RED}{BOLD}⚠️ Alerta de Conexão:{RESET} {state_dashboard['ultimo_erro']}")

def EXTRA_LOG_COLOR(log):
    if "FALHA" in log or "Erro" in log or "DDoS" in log:
        return "\033[91m"
    if "CONFIRMADA" in log or "SINAL" in log:
        return "\033[92m"
    return "\033[90m"

# ==============================================================================
# FUNÇÕES MATEMÁTICAS E DE SINAIS
# ==============================================================================
def calcular_rsi(prices, period=14):
    if len(prices) < period + 1:
        return np.full(len(prices), 50.0)
    
    delta = np.diff(prices)
    gain = (delta > 0) * delta
    loss = (delta < 0) * -delta
    
    avg_gain = np.zeros_like(prices)
    avg_loss = np.zeros_like(prices)
    
    avg_gain[period] = np.mean(gain[:period])
    avg_loss[period] = np.mean(loss[:period])
    
    for i in range(period + 1, len(prices)):
        avg_gain[i] = (avg_gain[i-1] * (period - 1) + gain[i-1]) / period
        avg_loss[i] = (avg_loss[i-1] * (period - 1) + loss[i-1]) / period
        
    rs = np.zeros_like(prices)
    rsi = np.zeros_like(prices)
    rsi[:period] = 50.0
    
    for i in range(period, len(prices)):
        if avg_loss[i] == 0:
            rsi[i] = 100.0
        else:
            rs[i] = avg_gain[i] / avg_loss[i]
            rsi[i] = 100.0 - (100.0 / (1.0 + rs[i]))
            
    return rsi

def calcular_adx(highs, lows, closes, p=14):
    n = len(closes)
    if n < p * 2: return np.zeros(n)
    tr = np.zeros(n)
    pdm = np.zeros(n)
    mdm = np.zeros(n)
    
    for i in range(1, n):
        tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        up = highs[i] - highs[i-1]
        dn = lows[i-1] - lows[i]
        pdm[i] = up if up > dn and up > 0 else 0.0
        mdm[i] = dn if dn > up and dn > 0 else 0.0
        
    def wilder_smoothing(data, p):
        res = np.zeros(len(data))
        res[p] = np.sum(data[1:p+1])
        for i in range(p+1, len(data)):
            res[i] = res[i-1] - (res[i-1]/p) + data[i]
        return res
        
    str_val = wilder_smoothing(tr, p)
    spdm = wilder_smoothing(pdm, p)
    smdm = wilder_smoothing(mdm, p)
    
    dx = np.zeros(n)
    for i in range(p, n):
        if str_val[i] > 0:
            pdi = 100 * spdm[i] / str_val[i]
            mdi = 100 * smdm[i] / str_val[i]
            if pdi + mdi > 0:
                dx[i] = 100 * abs(pdi - mdi) / (pdi + mdi)
                
    adx = np.zeros(n)
    if p*2 <= n:
        adx[p*2 - 1] = np.mean(dx[p:p*2])
        for i in range(p*2, n):
            adx[i] = (adx[i-1] * (p - 1) + dx[i]) / p
    return adx

def enviar_telegram(mensagem, token):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={
            "chat_id": TG_CHAT_ID,
            "text": mensagem,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }, timeout=5)
    except Exception as e:
        state_dashboard["ultimo_erro"] = f"Erro no envio do Telegram: {e}"

def disparar_webhook_motor_c(moeda, lado, tf, preco, r_vol, adx, rsi):
    try:
        payload = {
            "moeda": f"{moeda}USDT" if not moeda.endswith("USDT") else moeda,
            "lado": lado,
            "tf": tf,
            "preco_entrada": float(preco),
            "r_vol": float(r_vol),
            "adx": float(adx),
            "rsi": float(rsi),
            "motor": "MOTOR TESTE C"  # Integração direta com o novo Motor C
        }
        res = requests.post(WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
        if res.status_code == 200:
            return True
        else:
            state_dashboard["ultimo_erro"] = f"Webhook do site recusou envio (Status: {res.status_code})"
    except Exception as e:
        state_dashboard["ultimo_erro"] = f"Falha de rede com o Webhook {WEBHOOK_URL}"
    return False

# ==============================================================================
# CACHING DE COTAÇÃO E INTEGRAÇÃO DE MOEDAS (EVITA BLOQUEIO DE IP)
# ==============================================================================
cache_moedas = []
ultima_atualizacao_cache = 0  # Timestamp em segundos

def obter_moedas_volume_binance(limite=240):
    global cache_moedas, ultima_atualizacao_cache
    agora = time.time()
    
    tempo_decorrido_minutos = (agora - ultima_atualizacao_cache) / 60
    if len(cache_moedas) > 0 and tempo_decorrido_minutos < CACHE_MOEDAS_MINUTOS:
        return cache_moedas[:limite]
        
    try:
        tickers = exchange.fetch_tickers()
        futures_usdt_tickers = []
        for symbol, info in tickers.items():
            # Filtra contratos futuros USDS-M perpétuos USDT da Binance com segurança de padrão CCXT
            if symbol.endswith("/USDT") or symbol.endswith("/USDT:USDT"):
                base_coin = symbol.split('/')[0]
                # Ignorar stablecoins e moedas fiat pareadas para evitar falsos alarmes de extremos
                if base_coin in ["USDC", "USDT", "BUSD", "FDUSD", "TUSD", "DAI", "EUR", "AEUR", "USDP"]:
                    continue
                quote_volume = info.get('quoteVolume') or info.get('baseVolume', 0) * info.get('last', 1.0) or 0
                futures_usdt_tickers.append({
                    "moeda": base_coin,
                    "volume": float(quote_volume)
                })
        
        # Ordena de forma descendente por volume absoluto (Maior volume = Maior liquidez)
        futures_usdt_tickers.sort(key=lambda x: x["volume"], reverse=True)
        lista = [item["moeda"] for item in futures_usdt_tickers]
        
        # Salva no Cache para proteger o IP do usuário
        cache_moedas = lista
        ultima_atualizacao_cache = agora
        return lista[:limite]
        
    except ccxt.RateLimitExceeded as re:
        state_dashboard["rate_limits"] += 1
        state_dashboard["status"] = "RATE_LIMIT_DELAY"
        state_dashboard["ultimo_erro"] = "Rate limit Binance! Resfriando requisições..."
        time.sleep(45)
        if len(cache_moedas) > 0:
            return cache_moedas[:limite]
        return MOEDAS_ALVO_FIXO
    except ccxt.DDoSProtection as dd:
        state_dashboard["ddos_protections"] += 1
        state_dashboard["status"] = "RATE_LIMIT_DELAY"
        state_dashboard["ultimo_erro"] = "Proteção DDoS da Binance acionada! Aguardando..."
        time.sleep(90)
        if len(cache_moedas) > 0:
            return cache_moedas[:limite]
        return MOEDAS_ALVO_FIXO
    except Exception as e:
        state_dashboard["erros_conexao"] += 1
        state_dashboard["ultimo_erro"] = f"Erro ao acessar listagem de mercado: {e}"
        if len(cache_moedas) > 0:
            return cache_moedas[:limite]
        return MOEDAS_ALVO_FIXO

# ==============================================================================
# ALGORITMO PRINCIPAL DE MONITORAMENTO MULTI-TIMEFRAME (MTF) EXTREMO
# ==============================================================================
def varrer_moedas():
    state_dashboard["status"] = "VARRENDO"
    moedas_para_varrer = MOEDAS_ALVO_FIXO
    if USAR_LISTA_DINAMICA:
        moedas_para_varrer = obter_moedas_volume_binance(LIMITE_MOEDAS_DINAMICAS)
        
    state_dashboard["total_moedas"] = len(moedas_para_varrer)
    total_ativos = len(moedas_para_varrer)
    
    for idx, moeda in enumerate(moedas_para_varrer, start=1):
        state_dashboard["moeda_atual"] = moeda
        state_dashboard["progresso_index"] = idx
        
        # Redesenha o painel com o progresso real-time do ativo analisado
        desenhar_painel(moeda_sendo_varrida=moeda, progresso=idx, total=total_ativos)
        
        simbolo = f"{moeda}/USDT"
        try:
            # 1. OBTER CANDLES DO TEMPO GRÁFICO CURTO (5m)
            candles_curto = exchange.fetch_ohlcv(simbolo, timeframe=TF_CURTO, limit=60)
            if not candles_curto or len(candles_curto) < 30:
                continue
                
            df_curto = pd.DataFrame(candles_curto, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
            closes_curto = df_curto['close'].to_numpy()
            volumes_curto = df_curto['volume'].to_numpy()
            highs_curto = df_curto['high'].to_numpy()
            lows_curto = df_curto['low'].to_numpy()
            
            # Cálculo de Indicadores no Tempo Curto
            ma_curto = df_curto['close'].rolling(20).mean().to_numpy()
            std_curto = df_curto['close'].rolling(20).std().to_numpy()
            
            upper_band = ma_curto + (BOLLINGER_DESVIO * std_curto)
            lower_band = ma_curto - (BOLLINGER_DESVIO * std_curto)
            
            rsi_curto = calcular_rsi(closes_curto, 14)
            adx_curto = calcular_adx(highs_curto, lows_curto, closes_curto, 14)
            
            media_vol_curto20 = df_curto['volume'].rolling(20).mean().to_numpy()
            
            # Valores Atuais (Candle em Fechamento ou Penúltimo para consistência matemática estável)
            idx_candle = -2 # Penúltimo candle fechado, evitando falsos sinais de volatilidade inacabada
            preco_atual = closes_curto[idx_candle]
            vol_atual = volumes_curto[idx_candle]
            media_vol = media_vol_curto20[idx_candle]
            
            rvol = vol_atual / media_vol if media_vol > 0 else 1.0
            rsi_now = rsi_curto[idx_candle]
            adx_now = adx_curto[idx_candle] if len(adx_curto) > abs(idx_candle) else 25.0
            
            b_band_upper = upper_band[idx_candle]
            b_band_lower = lower_band[idx_candle]
            
            # Filtros Operacionais rápidos de extremos do 5m
            detec_long = (preco_atual <= b_band_lower) and (rsi_now <= RSI_EXTREMO_OVERSOLD) and (rvol >= RVOL_MINIMO)
            detec_short = (preco_atual >= b_band_upper) and (rsi_now >= RSI_EXTREMO_OVERBOUGHT) and (rvol >= RVOL_MINIMO)
            
            if detec_long or detec_short:
                lado = "LONG" if detec_long else "SHORT"
                
                # 2. VALIDAMOS NO TEMPO GRÁFICO MACRO (1H) PARA CONFIRMAÇÃO DE TENDÊNCIA
                # Reduz o perigo extremo de operar contra tendências destrutivas (Ex: Moedas derretendo sob pânico irracional)
                candles_macro = exchange.fetch_ohlcv(simbolo, timeframe=TF_MACRO, limit=100)
                if candles_macro and len(candles_macro) >= 30:
                    df_macro = pd.DataFrame(candles_macro, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
                    closes_macro = df_macro['close'].to_numpy()
                    rsi_macro = calcular_rsi(closes_macro, 14)[-1]
                    
                    confirmado = False
                    motivo_confirmacao = ""
                    
                    if lado == "LONG":
                        if rsi_macro > 30.0:
                            confirmado = True
                            motivo_confirmacao = f"Squeeze saudável de ressalto (Macro RSI estável em {rsi_macro:.1f})"
                        elif rsi_macro <= 25.0:
                            confirmado = True
                            motivo_confirmacao = f"Mega capitulação com repique eminente (RSI Macro exausto em {rsi_macro:.1f})"
                        else:
                            motivo_confirmacao = f"Faca caindo no Macro! RSI Macro em queda livre ({rsi_macro:.1f})"
                            
                    elif lado == "SHORT":
                        if rsi_macro < 70.0:
                            confirmado = True
                            motivo_confirmacao = f"Reversão em topo local com Macro seguro (Macro RSI em {rsi_macro:.1f})"
                        elif rsi_macro >= 75.0:
                            confirmado = True
                            motivo_confirmacao = f"Super exaustão esticada com topo duplo macro (Macro RSI em {rsi_macro:.1f})"
                        else:
                            motivo_confirmacao = f"Pressão de compra irracional detectada no Macro ({rsi_macro:.1f})"
                    
                    if confirmado:
                        # Incrementa métricas operacionais
                        state_dashboard["limites_atingidos"] += 1
                        
                        # Dispara Webhook estruturado de Ordem Imediata para o site
                        sucesso = disparar_webhook_motor_c(
                            moeda=moeda,
                            lado=lado,
                            tf=TF_CURTO,
                            preco=preco_atual,
                            r_vol=rvol,
                            adx=adx_now,
                            rsi=rsi_now
                        )
                        
                        if sucesso:
                            # Adiciona ao histórico do Dashboard Terminal
                            sinal_obj = {
                                "moeda": moeda,
                                "lado": lado,
                                "preco": preco_atual,
                                "rsi": rsi_now,
                                "rvol": rvol,
                                "hora": datetime.now().strftime("%H:%M:%S")
                            }
                            state_dashboard["historico_sinais"].append(sinal_obj)
                            
                            # Dispara alerta de Telegram ao canal do usuário
                            emoji = "🟢 LONG" if lado == "LONG" else "🔴 SHORT"
                            direcao_pense = "SUPORTE CRÍTICO E EXTREMO 🏄" if lado == "LONG" else "EXAUSTÃO DO PAVIO SUPERIOR 📉"
                            msg_tg = (
                                f"🤖 **SINAL DO ENGENHEIRO QUANT (MOTOR C)** 🤖\n\n"
                                f"🪙 **Ativo:** {moeda}USDT\n"
                                f"🧭 **Direção:** {emoji}\n"
                                f"💵 **Preço de Rebate:** ${preco_atual:.4f}\n"
                                f"📊 **R-VOL:** {rvol:.2f}x | **ADX:** {adx_now:.1f}\n"
                                f"🧬 **RSI Curto (5m):** {rsi_now:.1f}% | **RSI Macro (1h):** {rsi_macro:.1f}%\n"
                                f"💡 **Tese:** {direcao_pense}\n\n"
                                f"📲 *Enviado diretamente ao sistema de trading real/simulador!*"
                            )
                            enviar_telegram(msg_tg, TG_TOKEN_EXECUTADO)
                    else:
                        # Descarta o sinal devido a risco elevado na tendência macro
                        state_dashboard["ultimos_alertas"].append({
                            "moeda": moeda,
                            "preco": preco_atual,
                            "rsi": rsi_now,
                            "rvol": rvol,
                            "hora": datetime.now().strftime("%H:%M:%S"),
                            "motivo": f"Filtrado: {motivo_confirmacao}"
                        })
            
        except ccxt.RateLimitExceeded as re:
            state_dashboard["rate_limits"] += 1
            state_dashboard["ultimo_erro"] = f"RateLimit ao patrulhar {moeda}. Esperando resfriamento..."
            time.sleep(30)
        except ccxt.DDoSProtection as dd:
            state_dashboard["ddos_protections"] += 1
            state_dashboard["ultimo_erro"] = f"DDoSProtection em {moeda}. Pausa temporária ativa..."
            time.sleep(60)
        except Exception as e:
            pass # Ignora silenciosamente pequenas perdas pontuais de conexão em algum ativo específico o qual CCXT falhou
            
        # Delay adaptativo estratégico para garantir segurança total contra banimentos por IP
        # de acordo com o tamanho dinâmico do bloco a patrulhar
        delay_adaptativo = 0.15 if len(moedas_para_varrer) > 60 else 0.45
        time.sleep(delay_adaptativo)

# ==============================================================================
# LOOP RECORRENTE DE MONITORAMENTO INDEFINIDO
# ==============================================================================
if __name__ == "__main__":
    while True:
        try:
            varrer_moedas()
            
            # Atualiza estados para modo Respiro do Ciclo atual
            state_dashboard["status"] = "DELAY"
            state_dashboard["ciclo_atual"] += 1
            
            # Redesenha painel limpo com progresso concluído na espera de respiro
            total_ativos = state_dashboard["total_moedas"]
            desenhar_painel(moeda_sendo_varrida=None, progresso=total_ativos, total=total_ativos)
            
            time.sleep(45)
        except KeyboardInterrupt:
            # Terminação limpa, restaurando o terminal padrão
            print("\n👋 Robô de Engenharia de Análises Especiais (Motor C) finalizado pelo operador.")
            sys.exit(0)
        except Exception as e:
            state_dashboard["ultimo_erro"] = f"Erro crítico no loop de varreduras: {e}"
            time.sleep(10)
