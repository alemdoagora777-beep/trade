# -*- coding: utf-8 -*-
import sys, os, time, asyncio, threading, random, json, csv
from datetime import datetime
import ccxt
import flet as ft
import websocket
import pandas as pd
import requests
import logging
from flask import Flask, request, jsonify

# ==============================================================================
# 💎 SISTEMA: HONRANDO E PROSPERANDO PARA A GLÓRIA DE DEUS (V2 SNIPER)
# ==============================================================================
if sys.platform == 'win32':
    try: asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except: pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_MEMORIA = os.path.join(BASE_DIR, "memoria_real.json")
ARQUIVO_EXCEL = os.path.join(BASE_DIR, "Relatorio_REAL_Elite.xlsx")
ARQUIVO_AUDITORIA = os.path.join(BASE_DIR, "Auditoria_Quantitativa.csv")
ARQUIVO_SINAIS_AUDITORIA = os.path.join(BASE_DIR, "Auditoria_Sinais_Puros.csv") 

SISTEMA_LIGADO_EM = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
DOMINANCIA_DESDE = SISTEMA_LIGADO_EM 

VERSICULOS = [
    '"Consagre ao Senhor tudo o que você faz, e os planos Dele serão bem-sucedidos." (Prov. 16:3)',
    '"O agir de Deus é lindo e o Seu tempo é perfeito." (Ecl. 3:11)',
    '"Tudo posso Naquele que me fortalece." (Fil. 4:13)'
]

# --- CHAVES DE ACESSO E INTEGRAÇÕES ---
API_KEY    = "dLtdoF4WiwbdBf6GTcPHHWsZn2GxQaruFL35SO001nxPAZKakjVYPR4J5phYKOOD"
SECRET_KEY = "SJeCriW6Zq0onE0ukWdCYkP3Ts8cQq2XSPqAhKQ4Ew7vjOsbHrSpwWygIZuSD63r"

TG_TOKEN_ARMADO    = "8667082024:AAEMyrCuVMwHHpoAP56CDeDOCUNmsa-IJ5E" 
TG_TOKEN_EXECUTADO = "8888159023:AAHj5nAXI8zoBcWbK1ZTr8Y10kqdeND0354"
TG_CHAT_ID         = "7216099531" 

# --- ENDPOINT DE OUTFLOW DE WEBHOOKS (ATUALIZE COM A URL DA SUA PLATAFORMA SE ESTIVER RODANDO LOCAL!) ---
# Se rodar o motor no seu PC e quiser os sinais na plataforma atual, coloque a URL dela seguido de '/webhook'.
# Exemplo: RAILWAY_WEBHOOK_URL = "https://ais-pre-v7fmlssn3oehfn7sypgbtc-335113295610.us-west1.run.app/webhook"
RAILWAY_WEBHOOK_URL = "https://honrando-sinais-production.up.railway.app/webhook"
FLASK_WEBHOOK_SECRET   = "SNIPER_123"

# --- CONTROLES DE AUTOMAÇÃO GLOBAIS ---
RADAR_ATIVO = True
AUTO_REAL_ATIVO = False     
AUTO_SIMU_A_ATIVO = True    
AUTO_SIMU_B_ATIVO = True    

MAX_AUTO_REAL = 3           
MAX_AUTO_SIM = 10           
MARGEM_PADRAO = 1.0         
ALAVANCAGEM_PADRAO = 10     
ESTRATEGIA_REAL = "A"       

# --- PARÂMETROS DOCTRINAIS ---
STOP_LOSS_FIXO = -25.0
GATILHO_SURF = 100.0
PASSO_SURF = 5.0
META_DIARIA = 30.00
META_DIARIA_SIMU = 30.00
ALAVANCAGEM_GLOBAL = 20.0

CARTEIRA = []; HISTORICO = []; SINAIS_RECEBIDOS = []; LOGS_SINAIS_LISTA = []
RASTREIO_SINAIS = []; SINAIS_PENDENTES = [] 

STATS = {'real': {'w': 0, 'l': 0}, 'simu': {'w': 0, 'l': 0}, 'simu_b': {'w': 0, 'l': 0}}
TOTAL_SINAIS = {'LONG': 0, 'SHORT': 0} 

LAST_SIGNAL_TIME = {}
MOEDAS_PARA_SCAN = ["BTC", "ETH", "SOL", "BNB"] 
SCAN_STATE = {"status": "INICIANDO..."}
BTC_TREND = {"1h": "AGUARDANDO", "2h": "AGUARDANDO", "4h": "AGUARDANDO", "cor": "white54", "txt": "Calculando..."} 
BTC_MACRO_DIR = "NEUTRO"

PRECOS_WS = {}; WS_STATUS = {"ativo": False}; ui_lock = threading.RLock(); RELOAD_UI = False
BANCA_REAL = None 
ERRO_BANCA = ""

exchange = ccxt.binance({'apiKey': API_KEY, 'secret': SECRET_KEY, 'options': {'defaultType': 'future', 'adjustForTimeDifference': True}, 'enableRateLimit': True, 'timeout': 15000})

# ==============================================================================
# FUNÇÕES DE APOIO E API
# ==============================================================================
def safe_float(val):
    try: return float(val) if val else 0.0
    except: return 0.0

def enviar_telegram(mensagem, token):
    try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": TG_CHAT_ID, "text": mensagem, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=5)
    except: pass

def avisar_webhook(*args, **kwargs):
    try:
        moeda = ""
        tf = "30m"
        lado = "LONG"
        preco = 0.0
        tipo_alerta = "ALERTA_ARMADO"
        r_vol = 1.0
        adx = 25.0

        # Mapeamento dinâmico de argumentos posicionais para evitar crashes por quantidade de parâmetros
        if len(args) >= 1: moeda = args[0]
        if len(args) >= 2: tf = args[1]
        if len(args) >= 3: lado = args[2]
        if len(args) >= 4: preco = args[3]
        if len(args) >= 5: tipo_alerta = args[4]
        
        # Se receber 6 argumentos, ex: args=(moeda, tf, lado, ex_vela, "ALERTA_ARMADO", adx_now)
        if len(args) == 6:
            val = args[5]
            if "ARMADO" in str(tipo_alerta) or "GATILHO" in str(tipo_alerta):
                adx = val
            else:
                r_vol = val
        elif len(args) >= 7:
            r_vol = args[5]
            adx = args[6]

        payload = {
            "moeda": f"{moeda}USDT" if not str(moeda).endswith("USDT") else moeda,
            "timeframe": tf,
            "lado": lado,
            "preco_entrada": preco,
            "hora": datetime.now().strftime("%H:%M:%S"),
            "tipo": tipo_alerta,
            "r_vol": r_vol,
            "adx": adx
        }
        requests.post(RAILWAY_WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
    except Exception as e:
        pass

def avisar_railway(*args, **kwargs):
    avisar_webhook(*args, **kwargs)

def avisar_lovable(*args, **kwargs):
    avisar_webhook(*args, **kwargs)

def manter_banca_real():
    global BANCA_REAL, ERRO_BANCA
    while True:
        try:
            balanco = exchange.fetch_balance(params={'type': 'future'})
            achou = False
            if 'USDT' in balanco:
                BANCA_REAL = float(balanco['USDT'].get('total', 0.0)); ERRO_BANCA = ""; achou = True
            elif 'info' in balanco and 'assets' in balanco['info']:
                for ativo in balanco['info']['assets']:
                    if ativo.get('asset') == 'USDT':
                        BANCA_REAL = float(ativo.get('walletBalance', 0.0)); ERRO_BANCA = ""; achou = True; break
            if not achou: BANCA_REAL = 0.0; ERRO_BANCA = ""
            
            # Avisa a Railway sobre o saldo real atualizado para contornar o bloqueio de IP americano
            if achou:
                try:
                    payload = {
                        "tipo": "BALANCE_UPDATE",
                        "balance": BANCA_REAL,
                        "passphrase": FLASK_WEBHOOK_SECRET
                    }
                    requests.post(RAILWAY_WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
                except:
                    pass
        except ccxt.AuthenticationError: ERRO_BANCA = "🔑 API Inválida!"
        except Exception as e: ERRO_BANCA = str(e)[:40]
        time.sleep(5) 

def abrir_ordem_binance(simbolo, lado, margem, alavancagem):
    try:
        sym_binance = simbolo.replace(':USDT', '')
        exchange.set_leverage(int(alavancagem), sym_binance)
        try: exchange.set_margin_mode('isolated', sym_binance)
        except: pass
        preco_atual = float(exchange.fetch_ticker(simbolo)['last'])
        qtd_teorica = (float(margem) * float(alavancagem)) / preco_atual
        qtd_formatada = exchange.amount_to_precision(simbolo, qtd_teorica)
        lado_ordem = 'buy' if lado == 'LONG' else 'sell'
        ordem = exchange.create_order(simbolo, 'market', lado_ordem, float(qtd_formatada))
        preco_executado = float(ordem['average']) if 'average' in ordem and ordem['average'] else preco_atual
        return True, preco_executado, float(qtd_formatada)
    except Exception as e: return False, str(e), 0.0

def fechar_posicao_binance(simbolo, lado, qtd_salva=0.0):
    try:
        lado_fechar = 'sell' if lado == 'LONG' else 'buy'
        posicoes = exchange.fetch_positions([simbolo]) 
        for pos in posicoes:
            amt = abs(float(pos.get('contracts', 0.0) or pos.get('info',{}).get('positionAmt', 0.0)))
            if amt != 0:
                exchange.create_order(simbolo, 'market', lado_fechar, amt, params={'reduceOnly': True})
                return True
        return False
    except: return False

# ==============================================================================
# AUDITORIA E PLANILHAS
# ==============================================================================
def inicializar_csvs_auditoria():
    cab_sinais = ['Data', 'Hora_Alerta', 'Moeda', 'Timeframe', 'Lado', 'Preco_Alerta', 'Preco_Confirmacao', 'Volume_Confirmacao_RVOL', 'ADX_Alerta', 'RVOL_Alerta', 'Status_Final']
    if not os.path.exists(ARQUIVO_SINAIS_AUDITORIA):
        try:
            with open(ARQUIVO_SINAIS_AUDITORIA, mode='w', newline='', encoding='utf-8-sig') as f: csv.writer(f).writerow(cab_sinais)
        except: pass
    cab_operacoes = ['ID', 'Data', 'Robo_Origem', 'Hora_IN', 'Moeda', 'Lado', 'Preco_IN', 'Margem_US$', 'Motivo_OUT', 'Hora_OUT', 'Preco_OUT', 'PNL_Liquido', 'Tempo_Min', 'ROI_Max_%', 'ROI_Min_%']
    if not os.path.exists(ARQUIVO_AUDITORIA):
        try:
            with open(ARQUIVO_AUDITORIA, mode='w', newline='', encoding='utf-8-sig') as f: csv.writer(f).writerow(cab_operacoes)
        except: pass

def registrar_sinal_csv(sinal, status_final, preco_confirmacao=0.0, rvol_confirmacao=0.0):
    try:
        with open(ARQUIVO_SINAIS_AUDITORIA, mode='a', newline='', encoding='utf-8-sig') as f:
            csv.writer(f).writerow([datetime.now().strftime("%Y-%m-%d"), sinal.get('hora_in', ''), sinal.get('moeda', ''), sinal.get('tf', ''), sinal.get('lado', ''), safe_float(sinal.get('preco_in')), preco_confirmacao, round(rvol_confirmacao, 2), round(safe_float(sinal.get('adx')), 1), round(safe_float(sinal.get('r_vol')), 2), status_final])
    except: pass

def registrar_trade_csv(op, motivo, preco_out, pnl_liquido):
    try:
        agora_ts = time.time(); ts_in = op.get('ts_in', agora_ts) 
        tempo_minutos = round((agora_ts - ts_in) / 60, 2); data_hoje = datetime.now().strftime("%Y-%m-%d"); hora_out = datetime.now().strftime("%H:%M:%S")
        linha = [op.get('id', 'N/A'), data_hoje, f"AMARELO_{op.get('est', 'UNK')}", op.get('data_in', '--:--'), op.get('symbol', 'N/A').replace(':USDT', ''), op.get('side', 'N/A'), op.get('entry', 0.0), op.get('margin', 0.0), motivo, hora_out, preco_out, round(pnl_liquido, 2), tempo_minutos, round(safe_float(op.get('max_roi')), 2), round(safe_float(op.get('min_roi')), 2)]
        with open(ARQUIVO_AUDITORIA, mode='a', newline='', encoding='utf-8-sig') as f: csv.writer(f).writerow(linha)
    except: pass

# ==============================================================================
# MOTORES MATEMÁTICOS E DE SINAIS
# ==============================================================================
def calcular_sma(v, p): return sum(v[-p:]) / p if len(v) >= p else 0

def calcular_supertrend(highs, lows, closes, length=10, multiplier=3.0):
    n = len(closes); tr, atr, basic_ub, basic_lb, final_ub, final_lb, st_dir = [0.0]*n, [0.0]*n, [0.0]*n, [0.0]*n, [0.0]*n, [0.0]*n, [1]*n
    for i in range(1, n): tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
    atr[length] = sum(tr[1:length+1]) / length
    for i in range(length+1, n): atr[i] = (atr[i-1] * (length - 1) + tr[i]) / length
    for i in range(length, n):
        hl2 = (highs[i] + lows[i]) / 2.0; basic_ub[i] = hl2 + (multiplier * atr[i]); basic_lb[i] = hl2 - (multiplier * atr[i])
        final_ub[i] = basic_ub[i] if basic_ub[i] < final_ub[i-1] or closes[i-1] > final_ub[i-1] else final_ub[i-1]
        final_lb[i] = basic_lb[i] if basic_lb[i] > final_lb[i-1] or closes[i-1] < final_lb[i-1] else final_lb[i-1]
        if st_dir[i-1] == 1 and closes[i] < final_lb[i]: st_dir[i] = -1
        elif st_dir[i-1] == -1 and closes[i] > final_ub[i]: st_dir[i] = 1
        else: st_dir[i] = st_dir[i-1]
    return st_dir

def calcular_adx(highs, lows, closes, p=14):
    n = len(closes)
    if n < p * 2: return [0.0] * n
    tr, pdm, mdm = [0.0]*n, [0.0]*n, [0.0]*n
    for i in range(1, n):
        tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        up, dn = highs[i] - highs[i-1], lows[i-1] - lows[i]
        pdm[i] = up if up > dn and up > 0 else 0.0
        mdm[i] = dn if dn > up and dn > 0 else 0.0
    def ws(data, p):
        res = [0.0]*len(data); res[p] = sum(data[1:p+1])
        for i in range(p+1, len(data)): res[i] = res[i-1] - (res[i-1]/p) + data[i]
        return res
    str_, spdm, smdm = ws(tr, p), ws(pdm, p), ws(mdm, p)
    dx = [0.0]*n
    for i in range(p, n):
        if str_[i] > 0:
            pdi, mdi = 100 * spdm[i] / str_[i], 100 * smdm[i] / str_[i]
            if pdi + mdi > 0: dx[i] = 100 * abs(pdi - mdi) / (pdi + mdi)
    adx = [0.0]*n
    if p*2 <= n:
        adx[p*2 - 1] = sum(dx[p:p*2]) / p
        for i in range(p*2, n): adx[i] = (adx[i-1] * (p - 1) + dx[i]) / p
    return adx

def motor_filtro_btc():
    global BTC_TREND, BTC_MACRO_DIR
    while True:
        try:
            ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=250)
            if ohlcv and len(ohlcv) >= 200:
                closes = [c[4] for c in ohlcv]
                ema200 = sum(closes[-200:]) / 200
                BTC_MACRO_DIR = "LONG" if closes[-1] > ema200 else "SHORT"
                BTC_TREND['txt'] = f"[MACRO 1H]: {BTC_MACRO_DIR}"
                BTC_TREND['cor'] = "#00FF88" if BTC_MACRO_DIR == "LONG" else "#FF3366"
        except: pass
        time.sleep(60)

def motor_sinais_elite():
    global RELOAD_UI, SINAIS_RECEBIDOS, TOTAL_SINAIS, LAST_SIGNAL_TIME, SINAIS_PENDENTES, SCAN_STATE
    tfs_rastreio = ['30m', '1h', '2h'] 
    
    while True:
        try:
            if not RADAR_ATIVO: time.sleep(2); continue
            current_list = list(MOEDAS_PARA_SCAN)
            for i, moeda in enumerate(current_list):
                if not RADAR_ATIVO: break
                SCAN_STATE["status"] = f"🛰️ VARRENDO {i+1}/{len(current_list)}..."
                simbolo = f"{moeda}/USDT"
                
                for tf in tfs_rastreio:
                    try:
                        ohlcv = exchange.fetch_ohlcv(simbolo, timeframe=tf, limit=100)
                        if ohlcv and len(ohlcv) >= 30:
                            opens, highs, lows, closes, volumes = [c[1] for c in ohlcv], [c[2] for c in ohlcv], [c[3] for c in ohlcv], [c[4] for c in ohlcv], [c[5] for c in ohlcv]
                            vela_ts = ohlcv[-1][0]
                            
                            sma8, sma21 = calcular_sma(closes, 8), calcular_sma(closes, 21)
                            st_dirs = calcular_supertrend(highs, lows, closes, 10, multiplier=3.0)
                            adx_now = calcular_adx(highs, lows, closes, 14)[-1]
                            vol_sma20 = calcular_sma(volumes, 20)
                            open_now, vol_now = opens[-1], volumes[-1]
                            st_now, st_prev = st_dirs[-1], st_dirs[-2]
                            
                            flip_long = (st_now == 1 and st_prev == -1)
                            flip_short = (st_now == -1 and st_prev == 1)
                            
                            if flip_long or flip_short:
                                lado = "LONG" if flip_long else "SHORT"
                                sma_ok = (open_now > sma8 and open_now > sma21) if flip_long else (open_now < sma8 and open_now < sma21)
                                vol_aprovado = vol_now > vol_sma20
                                
                                if sma_ok and vol_aprovado:
                                    key_sinal = f"{moeda}_{tf}_{lado}"
                                    if LAST_SIGNAL_TIME.get(key_sinal) != vela_ts:
                                        LAST_SIGNAL_TIME[key_sinal] = vela_ts
                                        ex_vela = highs[-1] if lado == "LONG" else lows[-1]
                                        
                                        with ui_lock:
                                            TOTAL_SINAIS[lado] += 1
                                            rvol_calc = vol_now / vol_sma20 if vol_sma20 > 0 else 1.0
                                            h_in = datetime.now().strftime("%H:%M:%S")
                                            
                                            s_dict = {
                                                'id': f"{moeda}-{time.time()}", 'moeda': moeda, 'tf': tf, 
                                                'lado': lado, 'extremo': ex_vela, 'ts_in': time.time(), 
                                                'hora_in': h_in, 'r_vol': rvol_calc, 'adx': adx_now, 'preco_in': closes[-1]
                                            }
                                            SINAIS_PENDENTES.append(s_dict)
                                            SINAIS_RECEBIDOS.insert(0, {'hora': h_in, 'moeda': moeda, 'tf': tf.upper(), 'lado': lado, 'vol': f"VOL {rvol_calc:.1f}x", 'preco_in': closes[-1]})
                                            if len(SINAIS_RECEBIDOS) > 50: SINAIS_RECEBIDOS.pop()
                                            LOGS_SINAIS_LISTA.insert(0, f"[{h_in}] 🟡 ALERTA: {moeda} ({tf}) na Fila Sniper.")
                                            RELOAD_UI = True
                                        
                                        binance_link = f"https://www.binance.com/pt-BR/futures/{moeda}USDT"
                                        msg_tg = f"🟡 *SINAL DETECTADO - MESA SNIPER* 🟡\n\n🪙 *Moeda:* {moeda}\n⏱️ *Timeframe:* {tf}\n🧭 *Lado:* {lado}\n🚧 *Alvo de Rompimento (Extremo):* ${ex_vela:.4f}\n📈 *Preço do Sinal:* ${closes[-1]:.4f}\n📊 *R-VOL:* {rvol_calc:.1f}x | *ADX:* {adx_now:.1f}\n\n[Gráfico Binance]({binance_link})\n_Aguardando rompimento para disparar._"
                                        enviar_telegram(msg_tg, TG_TOKEN_ARMADO)
                                        threading.Thread(target=avisar_railway, args=(moeda, tf, lado, ex_vela, "ALERTA_ARMADO", rvol_calc, adx_now), daemon=True).start()
                    except: pass
                time.sleep(0.2)
                
            if RADAR_ATIVO:
                for s in range(120, 0, -1):
                    if not RADAR_ATIVO: break
                    SCAN_STATE["status"] = f"🕒 AGUARDANDO - {s}s"; time.sleep(1)
        except: time.sleep(10)

def motor_gatilho_sniper():
    global SINAIS_PENDENTES, CARTEIRA, RELOAD_UI
    while True:
        try:
            if not RADAR_ATIVO and not AUTO_REAL_ATIVO and not AUTO_SIMU_A_ATIVO and not AUTO_SIMU_B_ATIVO: time.sleep(5); continue
            
            for s in list(SINAIS_PENDENTES):
                moeda, tf, lado, extremo = s.get('moeda'), s.get('tf'), s.get('lado'), s.get('extremo')
                simb = f"{moeda}/USDT"
                
                ohlcv = exchange.fetch_ohlcv(simb, timeframe=tf, limit=100)
                if not ohlcv or len(ohlcv) < 30: continue
                
                closes, highs, lows, volumes = [c[4] for c in ohlcv], [c[2] for c in ohlcv], [c[3] for c in ohlcv], [c[5] for c in ohlcv]
                st_now = calcular_supertrend(highs, lows, closes, 10, multiplier=3.0)[-1]
                
                if (lado == "LONG" and st_now == -1) or (lado == "SHORT" and st_now == 1):
                    with ui_lock:
                        LOGS_SINAIS_LISTA.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] ❌ DESCARTADO: {moeda} inverteu.")
                        registrar_sinal_csv(s, "DESCARTADO_ST", 0.0, 0.0)
                        if s in SINAIS_PENDENTES: SINAIS_PENDENTES.remove(s)
                    threading.Thread(target=avisar_railway, args=(moeda, tf, lado, extremo, "ALERTA_DESCARTADO"), daemon=True).start()
                    RELOAD_UI = True; continue
                
                if (time.time() - s.get('ts_in', time.time())) > 43200:
                    with ui_lock:
                        registrar_sinal_csv(s, "EXPIRADO_12H", 0.0, 0.0)
                        if s in SINAIS_PENDENTES: SINAIS_PENDENTES.remove(s)
                    threading.Thread(target=avisar_railway, args=(moeda, tf, lado, extremo, "ALERTA_DESCARTADO"), daemon=True).start()
                    RELOAD_UI = True; continue
                
                v1_fechada, v2_fechada = ohlcv[-3][4], ohlcv[-2][4]
                v1_vol, v2_vol = ohlcv[-3][5], ohlcv[-2][5]
                
                gatilho_rompimento = False
                if lado == "LONG" and v1_fechada > extremo and v2_fechada > extremo: gatilho_rompimento = True
                elif lado == "SHORT" and v1_fechada < extremo and v2_fechada < extremo: gatilho_rompimento = True
                
                if gatilho_rompimento:
                    vol_medio_recente = calcular_sma(volumes[:-1], 20)
                    media_vol_rompimento = (v1_vol + v2_vol) / 2.0
                    
                    if media_vol_rompimento > vol_medio_recente:
                        with ui_lock:
                            h_exec = datetime.now().strftime("%H:%M:%S")
                            rvol_exec = media_vol_rompimento / vol_medio_recente if vol_medio_recente > 0 else 1.0
                            
                            registrar_sinal_csv(s, "EXECUTADO", closes[-1], rvol_exec)
                            
                            if AUTO_REAL_ATIVO and sum(1 for t in CARTEIRA if t.get('est') == 'REAL') < MAX_AUTO_REAL:
                                suc, p_ex, q = abrir_ordem_binance(simb, lado, MARGEM_PADRAO, ALAVANCAGEM_PADRAO)
                                if suc: CARTEIRA.append({'id': str(time.time())+'R', 'symbol': simb, 'side': lado, 'entry': p_ex, 'margin': MARGEM_PADRAO, 'roi': 0, 'pnl': 0, 'est': 'REAL', 'estrategia': ESTRATEGIA_REAL, 'lev': ALAVANCAGEM_PADRAO, 'ts_in': time.time(), 'data_in': h_exec, 'qtd_real': q, 'is_auto': True, 'stop_p': STOP_LOSS_FIXO, 'max_roi': 0.0, 'min_roi': 0.0})
                            if AUTO_SIMU_A_ATIVO and sum(1 for t in CARTEIRA if t.get('est') == 'SIMU') < MAX_AUTO_SIM:
                                CARTEIRA.append({'id': str(time.time())+'A', 'symbol': simb, 'side': lado, 'entry': closes[-1], 'margin': MARGEM_PADRAO, 'roi': 0, 'pnl': 0, 'est': 'SIMU', 'estrategia': 'A', 'lev': ALAVANCAGEM_PADRAO, 'ts_in': time.time(), 'data_in': h_exec, 'is_auto': True, 'stop_p': STOP_LOSS_FIXO, 'max_roi': 0.0, 'min_roi': 0.0})
                            if AUTO_SIMU_B_ATIVO and sum(1 for t in CARTEIRA if t.get('est') == 'SIMU_B') < MAX_AUTO_SIM:
                                CARTEIRA.append({'id': str(time.time())+'B', 'symbol': simb, 'side': lado, 'entry': closes[-1], 'margin': MARGEM_PADRAO, 'roi': 0, 'pnl': 0, 'est': 'SIMU_B', 'estrategia': 'B', 'lev': ALAVANCAGEM_PADRAO, 'ts_in': time.time(), 'data_in': h_exec, 'is_auto': True, 'stop_p': STOP_LOSS_FIXO, 'max_roi': 0.0, 'min_roi': 0.0})
                            
                            LOGS_SINAIS_LISTA.insert(0, f"[{h_exec}] ✅🟢 GATILHO ACIONADO: {moeda} rompeu com Volume.")
                            if s in SINAIS_PENDENTES: SINAIS_PENDENTES.remove(s)
                            RELOAD_UI = True
                            
                        msg_tg_exec = f"🟢 *ORDEM EXECUTADA - MESA SNIPER* 🟢\n\n🪙 *Moeda:* {moeda}\n⏱️ *Timeframe:* {tf}\n🧭 *Lado:* {lado}\n💵 *Preço de Entrada:* ${closes[-1]:.4f}\n📊 *R-VOL Confirmação:* {rvol_exec:.1f}x\n\n_Operações abertas nos módulos ativos._"
                        enviar_telegram(msg_tg_exec, TG_TOKEN_EXECUTADO)
                        threading.Thread(target=avisar_railway, args=(moeda, tf, lado, closes[-1], "GATILHO_SNIPER", rvol_exec, s.get('adx', 25.0)), daemon=True).start()
                        
            time.sleep(10)
        except: time.sleep(5)

def manter_top_200_volume():
    global MOEDAS_PARA_SCAN
    while True:
        try:
            tickers = exchange.fetch_tickers()
            liq = [(sym.split('/')[0], float(data['quoteVolume'])) for sym, data in tickers.items() if sym.endswith(':USDT') and data.get('quoteVolume')]
            liq = [m for m in liq if m[0] not in ['USDC', 'FDUSD', 'TUSD', 'BUSD'] and m[0].isalnum()]
            liq.sort(key=lambda x: x[1], reverse=True); top = [m[0] for m in liq[:200]]
            if len(top) >= 10: MOEDAS_PARA_SCAN = top
        except: pass
        time.sleep(1800)

# ==============================================================================
# 📡 MOTOR DE WEBHOOK (FLASK PARA SINAIS EXTERNOS)
# ==============================================================================
app = Flask(__name__)
@app.route('/webhook', methods=['POST'])
def receber_sinal_externo():
    global SINAIS_PENDENTES, SINAIS_RECEBIDOS, TOTAL_SINAIS, RELOAD_UI, LOGS_SINAIS_LISTA
    try:
        dados = request.json
        if not dados or dados.get("passphrase") != FLASK_WEBHOOK_SECRET: return "Denied", 403
            
        moeda = str(dados.get("moeda", "")).upper().replace('USDT', '')
        lado = str(dados.get("lado", "")).upper()
        tf = str(dados.get("tf", "30m")).upper()
        try: extremo = float(dados.get("extremo", 0.0))
        except: return "Erro Extremo", 400
        
        with ui_lock:
            h_in = datetime.now().strftime("%H:%M:%S")
            if lado in TOTAL_SINAIS: TOTAL_SINAIS[lado] += 1
            
            s_dict = {'id': str(time.time()) + "_EXT", 'moeda': moeda, 'tf': tf, 'lado': lado, 'extremo': extremo, 'ts_in': time.time(), 'hora_in': h_in, 'r_vol': 0.0, 'adx': 0.0, 'preco_in': extremo}
            SINAIS_PENDENTES.append(s_dict)
            SINAIS_RECEBIDOS.insert(0, {'hora': h_in, 'moeda': moeda, 'tf': tf, 'lado': lado, 'vol': "WEBHOOK EXT.", 'preco_in': extremo})
            if len(SINAIS_RECEBIDOS) > 50: SINAIS_RECEBIDOS.pop()
            LOGS_SINAIS_LISTA.insert(0, f"[{h_in}] 📡 WEBHOOK RECEBIDO: {moeda} ({lado}) na fila!")
            RELOAD_UI = True
            
        msg_tg = f"🟡 *SINAL EXTERNO RECEBIDO* 🟡\n\n🪙 *Moeda:* {moeda}\n⏱️ *Timeframe:* {tf}\n🧭 *Lado:* {lado}\n🚧 *Aguardando Rompimento:* ${extremo:.4f}\n\n_Robô Sniper pronto para engatilhar._"
        enviar_telegram(msg_tg, TG_TOKEN_ARMADO)
        return jsonify({"status": "sucesso"}), 200
    except: return "Erro", 500

def iniciar_servidor_webhook():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def iniciar_websocket():
    def on_message(ws, msg):
        try:
            dados = json.loads(msg)
            for item in dados: PRECOS_WS[item['s']] = float(item['c'])
        except: pass
    def run_ws(): ws = websocket.WebSocketApp("wss://fstream.binance.com/ws/!ticker@arr", on_message=on_message); ws.run_forever()
    threading.Thread(target=run_ws, daemon=True).start()

# ==============================================================================
# INTERFACE E INICIAÇÃO COMPLETA (FLET SUPREMO)
# ==============================================================================
def main(page: ft.Page):
    page.title = "HONRANDO E PROSPERANDO PARA A GLÓRIA DE DEUS (V2 SNIPER)"; page.theme_mode = "dark"
    BG_COLOR = "#050A1F"; CARD_COLOR = "#0B132B"; BORDER_COLOR = "#1C2541"   
    GOLD_PRIMARY = "#FFD700"; GOLD_SECONDARY = "#FFC107"; GOLD_TERTIARY = "#FF9800"   
    SAPPHIRE = "#00D1FF"; NEON_GREEN = "#00FF88"; NEON_RED = "#FF3366"        

    page.bgcolor = BG_COLOR; page.window_width = 1600; page.window_height = 980
    UI_TRADES = {}; UI_SINAIS = {} 
    
    def safe_upd(*args):
        for c in args:
            if getattr(c, 'page', None):
                try: c.update()
                except: pass

    # --- AUTOMAÇÕES UI ---
    def update_cfg(e):
        global RADAR_ATIVO, AUTO_REAL_ATIVO, AUTO_SIMU_A_ATIVO, AUTO_SIMU_B_ATIVO, MAX_AUTO_REAL, MARGEM_PADRAO, ALAVANCAGEM_PADRAO, ESTRATEGIA_REAL
        RADAR_ATIVO = sw_radar.value; AUTO_REAL_ATIVO = sw_auto_real.value
        AUTO_SIMU_A_ATIVO = sw_auto_sim_a.value; AUTO_SIMU_B_ATIVO = sw_auto_sim_b.value
        ESTRATEGIA_REAL = rg_est_real.value
        try: MAX_AUTO_REAL = int(tf_max_real.value); MARGEM_PADRAO = float(tf_margem.value.replace(",",".")); ALAVANCAGEM_PADRAO = int(tf_alav.value)
        except: pass
        page.update()

    sw_radar = ft.Switch(label="Radar Automático", value=RADAR_ATIVO, active_color=GOLD_PRIMARY, on_change=update_cfg)
    sw_auto_real = ft.Switch(label="ON", value=AUTO_REAL_ATIVO, active_color=SAPPHIRE, on_change=update_cfg)
    sw_auto_sim_a = ft.Switch(label="ON", value=AUTO_SIMU_A_ATIVO, active_color=SAPPHIRE, on_change=update_cfg)
    sw_auto_sim_b = ft.Switch(label="ON", value=AUTO_SIMU_B_ATIVO, active_color=SAPPHIRE, on_change=update_cfg)
    rg_est_real = ft.RadioGroup(content=ft.Row([ft.Radio(value="A", label="Estratégia A (Alvo 100% | SL -25%)"), ft.Radio(value="B", label="Estratégia B (Parciais 15% e 30% | BE)")], spacing=40), value=ESTRATEGIA_REAL, on_change=update_cfg)
    tf_max_real = ft.TextField(value=str(MAX_AUTO_REAL), width=800, text_align="center", on_change=update_cfg, border_color=BORDER_COLOR)
    tf_margem = ft.TextField(value=str(MARGEM_PADRAO), width=200, on_change=update_cfg, border_color=BORDER_COLOR)
    tf_alav = ft.TextField(value=str(ALAVANCAGEM_PADRAO), width=200, on_change=update_cfg, border_color=BORDER_COLOR)
    
    view_automacao = ft.Column([
        ft.Text("AUTOMAÇÃO DE SINAIS DO RADAR", size=24, weight="bold", color=GOLD_TERTIARY),
        ft.Container(height=20),
        ft.Row([
            ft.Container(content=ft.Row([ft.Text("AUTOMÁTICO • REAL", weight="bold", color="white54"), sw_auto_real], alignment="spaceBetween"), width=300, padding=15, border=ft.border.all(1, BORDER_COLOR), border_radius=10),
            ft.Container(content=ft.Row([ft.Text("AUTOMÁTICO • SIMULADOR A", weight="bold", color="white54"), sw_auto_sim_a], alignment="spaceBetween"), width=380, padding=15, border=ft.border.all(1, BORDER_COLOR), border_radius=10),
            ft.Container(content=ft.Row([ft.Text("AUTOMÁTICO • TESTE B", weight="bold", color="white54"), sw_auto_sim_b], alignment="spaceBetween"), width=300, padding=15, border=ft.border.all(1, BORDER_COLOR), border_radius=10),
        ], spacing=20),
        ft.Container(height=20),
        ft.Container(content=ft.Column([ft.Row([ft.Text("🎯", size=18), ft.Text("SAÍDA PARA OPERAÇÕES REAIS", color=NEON_GREEN, weight="bold")]), ft.Container(height=10), rg_est_real, ft.Container(height=20), ft.Row([ft.Text("📈", size=18), ft.Text("LIMITE REAIS SIMULTÂNEAS", color="white54", weight="bold")]), tf_max_real]), padding=30, border=ft.border.all(1, NEON_GREEN), border_radius=15, bgcolor="#03120A"),
        ft.Container(height=20),
        ft.Row([ft.Container(content=ft.Column([ft.Text("$ MARGEM (US$)", color="white54", size=12), tf_margem]), padding=20, border=ft.border.all(1, BORDER_COLOR), border_radius=10), ft.Container(content=ft.Column([ft.Text("⤤ ALAVANCAGEM (X)", color="white54", size=12), tf_alav]), padding=20, border=ft.border.all(1, BORDER_COLOR), border_radius=10)], spacing=20)
    ], expand=True, scroll="always")

    # --- VARIÁVEIS DE TELA ---
    lbl_banca = ft.Text("Conectando API...", size=36, weight="bold", color="white54") 
    lbl_pnl_total_real = ft.Text("$+0.00", size=28, weight="bold", color=NEON_GREEN)
    lbl_pnl_total_simu = ft.Text("$+0.00", size=28, weight="bold", color=NEON_GREEN)
    lbl_pnl_total_simu_b = ft.Text("$+0.00", size=28, weight="bold", color=NEON_GREEN)
    lbl_relogio = ft.Text("00:00:00", size=18, weight="bold", color="white")
    lbl_scanning = ft.Text("INICIANDO PATRULHA...", size=14, color=GOLD_SECONDARY, italic=True)
    lbl_btc_msg = ft.Text("ANALISANDO BTC...", size=14, color="white", weight="bold")
    
    pl_w = ft.Text("🏆 W: 0", color=NEON_GREEN, weight="bold", size=15); pl_l = ft.Text("💀 L: 0", color=NEON_RED, weight="bold", size=15)
    pl_wr = ft.Text("🎯 WR: 0.0%", color=GOLD_PRIMARY, weight="bold", size=15); pl_liq = ft.Text("💰 LÍQUIDO: $0.00", color="white", weight="bold", size=15) 
    pl_flu = ft.Text("🌊 FLUTUANTE: $0.00", color=GOLD_PRIMARY, weight="bold", size=15); pl_count = ft.Text("ATIVAS: 0", color=GOLD_PRIMARY, weight="bold", size=15)

    pl_s_w = ft.Text("🏆 W: 0", color=NEON_GREEN, weight="bold", size=15); pl_s_l = ft.Text("💀 L: 0", color=NEON_RED, weight="bold", size=15)
    pl_s_wr = ft.Text("🎯 WR: 0.0%", color=GOLD_SECONDARY, weight="bold", size=15); pl_s_liq = ft.Text("💰 LÍQUIDO: $0.00", color="white", weight="bold", size=15) 
    pl_s_flu = ft.Text("🌊 FLUTUANTE: $0.00", color=GOLD_SECONDARY, weight="bold", size=15); pl_s_count = ft.Text("ATIVAS: 0", color=GOLD_SECONDARY, weight="bold", size=15)

    pl_b_w = ft.Text("🏆 W: 0", color=NEON_GREEN, weight="bold", size=15); pl_b_l = ft.Text("💀 L: 0", color=NEON_RED, weight="bold", size=15)
    pl_b_wr = ft.Text("🎯 WR: 0.0%", color=GOLD_TERTIARY, weight="bold", size=15); pl_b_liq = ft.Text("💰 LÍQUIDO: $0.00", color="white", weight="bold", size=15) 
    pl_b_flu = ft.Text("🌊 FLUTUANTE: $0.00", color=GOLD_TERTIARY, weight="bold", size=15); pl_b_count = ft.Text("ATIVAS: 0", color=GOLD_TERTIARY, weight="bold", size=15)

    list_ativas = ft.Column(spacing=10, scroll="always", expand=True); list_historico = ft.Column(spacing=10, scroll="always", expand=True)
    list_ativas_simu = ft.Column(spacing=10, scroll="always", expand=True); list_hist_simu = ft.Column(spacing=10, scroll="always", expand=True)
    list_ativas_simu_b = ft.Column(spacing=10, scroll="always", expand=True); list_hist_simu_b = ft.Column(spacing=10, scroll="always", expand=True)
    list_sinais_ui = ft.Column(spacing=10, scroll="always", expand=True); list_fila_sniper = ft.Column(spacing=10, scroll="always", expand=True) 
    list_logs_home = ft.Column(spacing=5, scroll="always")
    palco = ft.Container(expand=True, padding=35, bgcolor=BG_COLOR)

    def btn_nav(emoji, label, target): return ft.Container(content=ft.Row([ft.Text(emoji, size=20), ft.Text(label, color=GOLD_PRIMARY, weight="bold", size=15)], spacing=15), padding=15, border_radius=10, on_click=lambda _: [setattr(palco, "content", target), page.update()])

    def get_cockpit():
        return ft.Column([
            ft.Row([ft.Text("HONRANDO E PROSPERANDO PARA A GLÓRIA DE DEUS", size=30, weight="bold", color=GOLD_PRIMARY, text_align=ft.TextAlign.CENTER)], alignment="center"),
            ft.Container(content=ft.Row([ft.Text(random.choice(VERSICULOS), size=16, color=GOLD_PRIMARY, italic=True, text_align="center")], alignment="center"), padding=10),
            ft.Row([ft.Container(content=ft.Column([ft.Row([ft.Text("PATRIMÔNIO (REAL)", size=12, color="white")], alignment="center"), ft.Row([lbl_banca], alignment="center")]), bgcolor=CARD_COLOR, padding=15, border_radius=15, expand=1, border=ft.border.all(1, BORDER_COLOR)), ft.Container(content=ft.Column([ft.Row([lbl_relogio], alignment="center"), ft.Row([lbl_btc_msg], alignment="center")]), bgcolor=CARD_COLOR, padding=15, border_radius=15, expand=1, border=ft.border.all(1, BORDER_COLOR))], spacing=20),
            ft.Container(height=5),
            ft.Row([ft.Container(content=ft.Column([ft.Text("LUCRO SESSÃO (REAL)", size=12, color="white", weight="bold"), lbl_pnl_total_real]), bgcolor="#0A0F1D", padding=20, border_radius=15, expand=1, border=ft.border.all(1, GOLD_PRIMARY)), ft.Container(content=ft.Column([ft.Text("LUCRO SESSÃO (SIMU)", size=12, color="white", weight="bold"), lbl_pnl_total_simu]), bgcolor="#0A0F1D", padding=20, border_radius=15, expand=1, border=ft.border.all(1, GOLD_SECONDARY)), ft.Container(content=ft.Column([ft.Text("LUCRO SESSÃO (TESTE B)", size=12, color="white", weight="bold"), lbl_pnl_total_simu_b]), bgcolor="#0A0F1D", padding=20, border_radius=15, expand=1, border=ft.border.all(1, GOLD_TERTIARY))], spacing=20),
            ft.Container(height=5),
            ft.Container(content=ft.Row([ft.Row([ft.ProgressRing(width=20, height=20, color=GOLD_SECONDARY, stroke_width=3), ft.Column([ft.Row([ft.Text("RADAR TELEGRAM ELITE", color="white", weight="bold", size=16)]), lbl_scanning], spacing=2)], spacing=15, expand=True), sw_radar]), bgcolor=CARD_COLOR, padding=20, border_radius=15, border=ft.border.all(1, BORDER_COLOR)),
            ft.Container(height=5), ft.Text("LOGS DE VARREDURA E GATILHOS:", size=14, color="white", weight="bold"),
            ft.Container(content=list_logs_home, bgcolor="black", padding=15, border_radius=10, expand=True) 
        ], expand=True)

    def header_tab(cor): return ft.Container(content=ft.Row([ft.Text("MOEDA", width=120, weight="bold", color=cor), ft.Text("HORA", width=80, weight="bold", color=cor), ft.Text("LADO", width=70, weight="bold", color=cor), ft.Text("ROI %", width=80, weight="bold", color=cor), ft.Text("MIN/MAX", width=100, weight="bold", color=cor), ft.Text("PNL/MG", width=110, weight="bold", color=cor), ft.Text("STATUS / TRAVA", expand=1, weight="bold", color=cor), ft.Text("X", width=40, weight="bold", color=cor, text_align="center")]), padding=15, bgcolor="#0A0F1D", border_radius=10)
    def header_hist(cor): return ft.Container(content=ft.Row([ft.Text("MOEDA", width=120, weight="bold", color=cor), ft.Text("IN", width=50, weight="bold", color=cor), ft.Text("OUT", width=50, weight="bold", color=cor), ft.Text("LADO", width=70, weight="bold", color=cor), ft.Text("ROI (MÍN/MÁX)", width=120, weight="bold", color=cor), ft.Text("LUCRO", width=80, weight="bold", color=cor), ft.Text("MOTIVO / OBS", expand=1, weight="bold", color=cor)]), padding=10, bgcolor="#0A0F1D", border_radius=10)
    def header_sinais(): return ft.Container(content=ft.Row([ft.Text("HORÁRIO", width=70, weight="bold", color=GOLD_SECONDARY), ft.Text("MOEDA", width=110, weight="bold", color=GOLD_SECONDARY), ft.Text("TEMPO", width=60, weight="bold", color=GOLD_SECONDARY), ft.Text("DIREÇÃO", width=80, weight="bold", color=GOLD_SECONDARY), ft.Text("PREÇO (IN)", width=120, weight="bold", color=GOLD_SECONDARY), ft.Text("PNL VIVO", width=80, weight="bold", color=GOLD_SECONDARY), ft.Text("AÇÃO", width=100, weight="bold", color=GOLD_SECONDARY)]), padding=15, bgcolor="#0A0F1D", border_radius=10)
    def header_sniper(): return ft.Container(content=ft.Row([ft.Text("HORA", width=100, weight="bold", color=GOLD_PRIMARY), ft.Text("MOEDA", width=120, weight="bold", color=GOLD_PRIMARY), ft.Text("TF", width=60, weight="bold", color=GOLD_PRIMARY), ft.Text("LADO", width=80, weight="bold", color=GOLD_PRIMARY), ft.Text("ROMPIMENTO", width=200, weight="bold", color=GOLD_PRIMARY), ft.Text("STATUS", expand=1, weight="bold", color=GOLD_PRIMARY), ft.Text("REMOVER", width=80, weight="bold", color=GOLD_PRIMARY, text_align="center")]), padding=15, bgcolor="#0A0F1D", border_radius=10)

    view_ativas = ft.Column([ft.Text("🔴 OPERAÇÕES ATIVAS (BINANCE REAL)", size=26, weight="bold", color="white"), ft.Container(content=ft.Row([pl_w, pl_l, pl_wr, pl_liq, pl_flu, pl_count], alignment="spaceAround"), bgcolor=CARD_COLOR, padding=20, border_radius=15), ft.Container(height=10), header_tab(GOLD_PRIMARY), list_ativas], expand=True)
    view_hist = ft.Column([ft.Text("🔴 HISTÓRICO REAL", size=26, weight="bold", color="white"), ft.Container(height=10), header_hist(GOLD_PRIMARY), list_historico], expand=True)
    view_simu = ft.Column([ft.Text("🎮 AMBIENTE DE SIMULAÇÃO (PAPEL)", size=26, weight="bold", color="white"), ft.Container(content=ft.Row([pl_s_w, pl_s_l, pl_s_wr, pl_s_liq, pl_s_flu, pl_s_count], alignment="spaceAround"), bgcolor=CARD_COLOR, padding=20, border_radius=15), ft.Container(height=10), header_tab(GOLD_SECONDARY), list_ativas_simu, ft.Container(height=20), ft.Text("HISTÓRICO SIMULADOR", size=16, weight="bold", color="white54"), header_hist(GOLD_SECONDARY), list_hist_simu], expand=True, scroll="always")
    view_simu_b = ft.Column([ft.Text("🧪 AMBIENTE TESTE B (ESTRATÉGIA QUANT)", size=26, weight="bold", color="white"), ft.Container(content=ft.Row([pl_b_w, pl_b_l, pl_b_wr, pl_b_liq, pl_b_flu, pl_b_count], alignment="spaceAround"), bgcolor=CARD_COLOR, padding=20, border_radius=15), ft.Container(height=10), header_tab(GOLD_TERTIARY), list_ativas_simu_b, ft.Container(height=20), ft.Text("HISTÓRICO TESTE B", size=16, weight="bold", color="white54"), header_hist(GOLD_TERTIARY), list_hist_simu_b], expand=True, scroll="always")
    view_sinais = ft.Column([ft.Text("📡 SINAIS RECEBIDOS", size=26, weight="bold", color="white"), ft.Container(height=10), header_sinais(), list_sinais_ui], expand=True)
    view_fila_sniper = ft.Column([ft.Text("🟡 FILA SNIPER (AGUARDANDO ROMPIMENTO)", size=26, weight="bold", color=GOLD_PRIMARY), ft.Text("Robô só entrará se 2 velas fecharem rompendo a linha demarcada com volume.", color="white54", italic=True), ft.Container(height=10), header_sniper(), list_fila_sniper], expand=True) 

    sidebar = ft.Container(width=280, bgcolor="#030614", padding=25, border=ft.Border(right=ft.BorderSide(1, BORDER_COLOR)), content=ft.Column([
        ft.Row([ft.Text("DEUS ESTÁ NO CONTROLE ✝️", size=17, weight="bold", color=GOLD_SECONDARY)], alignment="center"), 
        ft.Row([ft.Text("MODO HÍBRIDO", size=12, weight="bold", color=GOLD_PRIMARY)], alignment="center"), 
        ft.Divider(height=40, color=BORDER_COLOR),
        btn_nav("🦅", "INÍCIO", get_cockpit()), 
        btn_nav("⚙️", "AUTOMAÇÕES", view_automacao), 
        btn_nav("🟡", "FILA SNIPER", view_fila_sniper), 
        btn_nav("📡", "SINAIS", view_sinais), 
        btn_nav("⚡", "ATIVAS REAL", view_ativas), 
        btn_nav("📖", "HIST. REAL", view_hist),
        btn_nav("🎮", "SIMULADOR", view_simu), 
        btn_nav("🧪", "TESTE B", view_simu_b), 
        ft.Container(expand=True), 
        ft.Row([ft.Text("GLÓRIA A DEUS", size=12, color=GOLD_PRIMARY, weight="bold")], alignment="center")
    ], scroll="always")) 

    def encerrar_posicao_interface(tid, motivo="Saída Manual"):
        global CARTEIRA
        op_fechar = None
        with ui_lock:
            for i, t in enumerate(CARTEIRA):
                if str(t.get('id', '')) == str(tid):
                    op_fechar = CARTEIRA.pop(i)
                    break
        if op_fechar:
            if op_fechar.get('est') == 'REAL':
                fechar_posicao_binance(op_fechar.get('symbol'), op_fechar.get('side'), safe_float(op_fechar.get('qtd_real')))
            preco_out = safe_float(op_fechar.get('now', op_fechar.get('entry', 0))) 
            pnl_final = safe_float(op_fechar.get('pnl', 0.0))
            registrar_trade_csv(op_fechar, motivo, preco_out, pnl_final)
            with ui_lock:
                est_f = op_fechar.get('est', 'simu').lower()
                if pnl_final > 0: STATS[est_f]['w'] += 1
                else: STATS[est_f]['l'] += 1
                op_fechar['motivo'] = motivo; op_fechar['data_fim'] = datetime.now().strftime("%H:%M:%S")
                HISTORICO.append(op_fechar)
            safe_upd(page)

    def deletar_fila_sniper(sid):
        global SINAIS_PENDENTES, RELOAD_UI
        with ui_lock: SINAIS_PENDENTES = [s for s in SINAIS_PENDENTES if str(s.get('id', '')) != str(sid)]
        RELOAD_UI = True

    def render_tables():
        with ui_lock:
            temp_atv_r, temp_atv_s, temp_atv_b = [], [], []
            UI_TRADES.clear() 
            for t in CARTEIRA:
                if type(t) is not dict: continue
                ui_roi, ui_maxmin, ui_pnl, ui_status = ft.Text(f"{safe_float(t.get('roi')):.2f}%", width=80, color=(NEON_GREEN if safe_float(t.get('roi')) >= 0 else NEON_RED), weight="bold", size=14), ft.Text(f"{safe_float(t.get('min')):.1f}% / {safe_float(t.get('max')):.1f}%", width=100, size=11, color="white54", weight="bold"), ft.Text(f"${safe_float(t.get('pnl')):.2f}", weight="bold", size=14, color="white"), ft.Text("⏳ ANALISANDO", size=12, weight="heavy", color="white54")
                UI_TRADES[str(t.get('id', ''))] = {'roi': ui_roi, 'maxmin': ui_maxmin, 'pnl': ui_pnl, 'status': ui_status}
                tipo_tag = "🤖 " if t.get('is_auto', False) else "⌨️ "
                cor_l = NEON_GREEN if "LONG" in str(t.get('side','')) else NEON_RED
                row = ft.Container(content=ft.Row([
                    ft.Text(tipo_tag + str(t.get('symbol','')).split('/')[0], width=120, weight="bold", size=14), 
                    ft.Text(str(t.get('data_in', '--:--')), width=80, size=12, color="white54"), 
                    ft.Text(str(t.get('side','')), width=70, color=cor_l, weight="bold", size=14), 
                    ui_roi, ui_maxmin, 
                    ft.Column([ui_pnl, ft.Text(f"Mg: ${safe_float(t.get('margin')):.2f} | {int(safe_float(t.get('lev', 20)))}x", size=10, color="white54")], width=110), 
                    ft.Column([ui_status], expand=1), 
                    ft.Container(content=ft.Row([ft.Text("X", color="white", weight="bold")], alignment="center"), width=40, bgcolor=NEON_RED, padding=ft.padding.symmetric(8,0), border_radius=6, on_click=lambda e, tid=str(t.get('id')): encerrar_posicao_interface(tid, "Saída Manual"))
                ]), padding=10, bgcolor=CARD_COLOR, border_radius=8, border=ft.border.all(1, BORDER_COLOR))
                
                if t.get('est') == 'REAL': temp_atv_r.append(row)
                elif t.get('est') == 'SIMU': temp_atv_s.append(row)
                elif t.get('est') == 'SIMU_B': temp_atv_b.append(row)
                
            list_ativas.controls, list_ativas_simu.controls, list_ativas_simu_b.controls = temp_atv_r, temp_atv_s, temp_atv_b
            
            temp_hst_r, temp_hst_s, temp_hst_b = [], [], []
            for h in reversed(HISTORICO[-100:]): 
                if type(h) is not dict: continue
                tipo_tag = "🤖 " if h.get('is_auto', False) else "⌨️ "
                cor_l = NEON_GREEN if "LONG" in str(h.get('side','')) else NEON_RED
                txt_obs = f"{str(h.get('motivo','-'))}"
                roi_info = ft.Column([ft.Text(f"{safe_float(h.get('roi')):.2f}%", color=(NEON_GREEN if safe_float(h.get('pnl')) > 0 else NEON_RED), weight="bold", size=14), ft.Text(f"{safe_float(h.get('min_roi')):.1f}% / {safe_float(h.get('max_roi')):.1f}%", size=10, color="white54")], width=120)
                
                row = ft.Container(content=ft.Row([
                    ft.Text(tipo_tag + str(h.get('symbol','')).split('/')[0], width=120, weight="bold", size=14), 
                    ft.Text(str(h.get('data_in','-')), width=50, size=12, color="white54"), 
                    ft.Text(str(h.get('data_fim','-')), width=50, size=12, color="white54"), 
                    ft.Text(str(h.get('side','')), width=70, color=cor_l, weight="bold", size=13), 
                    roi_info, 
                    ft.Text(f"${safe_float(h.get('pnl')):.2f}", width=80, color=(NEON_GREEN if safe_float(h.get('pnl')) > 0 else NEON_RED), weight="bold", size=14), 
                    ft.Text(txt_obs, expand=1, size=10, italic=True, color="white54")
                ]), padding=10, bgcolor="#0A0F1D", border_radius=8, border=ft.border.all(1, BORDER_COLOR))
                
                if h.get('est') == 'REAL': temp_hst_r.append(row)
                elif h.get('est') == 'SIMU': temp_hst_s.append(row)
                elif h.get('est') == 'SIMU_B': temp_hst_b.append(row)
                
            list_historico.controls, list_hist_simu.controls, list_hist_simu_b.controls = temp_hst_r, temp_hst_s, temp_hst_b

            temp_fila = []
            for s in SINAIS_PENDENTES:
                if type(s) is not dict: continue
                cor_l = NEON_GREEN if "LONG" in str(s.get('lado','')) else NEON_RED
                px_atual = PRECOS_WS.get(str(s.get('moeda','')).replace('/', '').replace(':USDT', '') + 'USDT', 0.0)
                btn_del = ft.Container(content=ft.Row([ft.Text("X", color="white", weight="bold")], alignment="center"), width=50, bgcolor=NEON_RED, padding=ft.padding.symmetric(8,0), border_radius=6, on_click=lambda e, sid=str(s.get('id')): deletar_fila_sniper(sid))
                
                row = ft.Container(content=ft.Row([
                    ft.Text(str(s.get('hora_in', '--:--')), width=100, size=14, color="white54"),
                    ft.Text(str(s.get('moeda','')), width=120, weight="bold", size=15, color=GOLD_PRIMARY),
                    ft.Text(str(s.get('tf','')), width=60, size=14, color="white"),
                    ft.Text(str(s.get('lado','')), width=80, color=cor_l, weight="bold", size=15),
                    ft.Text(f"Rompimento: ${safe_float(s.get('extremo')):.4f}", width=200, size=14, color="white"),
                    ft.Text(f"Preço Atual: ${px_atual:.4f} - Aguardando 2 Velas", expand=1, size=12, color="white54", italic=True),
                    btn_del
                ]), padding=10, bgcolor=CARD_COLOR, border_radius=8, border=ft.border.all(1, GOLD_PRIMARY))
                temp_fila.append(row)
            list_fila_sniper.controls = temp_fila

            temp_sinais = []
            UI_SINAIS.clear()
            for s in SINAIS_RECEBIDOS:
                if type(s) is not dict: continue
                chave_s = f"{str(s.get('hora','-'))}_{str(s.get('moeda','-'))}_{str(s.get('tf','-'))}"
                cor_l = NEON_GREEN if "LONG" in str(s.get('lado','')) else NEON_RED
                tv_interval = "30" if str(s.get('tf')).lower() == "30m" else ("120" if str(s.get('tf')).lower() == "2h" else "60") 
                
                ui_px_now = ft.Text(f"NOW: ${safe_float(s.get('preco_in')):.4f}", size=11, color="white", weight="bold")
                ui_pnl_s = ft.Text(f"+0.00%", width=80, color=NEON_GREEN, weight="bold", size=15)
                UI_SINAIS[chave_s] = {'now': ui_px_now, 'pnl': ui_pnl_s}
                
                btn_tv = ft.ElevatedButton("TradingView", url=f"https://www.tradingview.com/chart/?symbol=BINANCE:{str(s.get('moeda','-'))}USDT.P&interval={tv_interval}", bgcolor="#1E222D", color="white", height=30)
                
                row = ft.Container(content=ft.Row([
                    ft.Text(str(s.get('hora','-')), width=70, size=14, color="white54"), 
                    ft.Text(str(s.get('moeda','-')), width=110, weight="bold", size=15, color="white"), 
                    ft.Text(str(s.get('tf','-')), width=60, size=14, color=GOLD_SECONDARY, weight="bold"), 
                    ft.Text(str(s.get('lado','-')), width=80, color=cor_l, weight="bold", size=15), 
                    ft.Column([ft.Text(f"IN: ${safe_float(s.get('preco_in')):.4f}", size=11, color="white54"), ui_px_now], width=120),
                    ui_pnl_s,
                    btn_tv
                ]), padding=10, bgcolor=CARD_COLOR, border_radius=8, border=ft.border.all(1, BORDER_COLOR))
                temp_sinais.append(row)
            list_sinais_ui.controls = temp_sinais

    palco.content = get_cockpit(); page.add(ft.Row([sidebar, palco], expand=True, spacing=0)); render_tables()

    def refresh():
        global RELOAD_UI
        ultimo_rest = 0
        while True:
            try:
                if RELOAD_UI: 
                    try: render_tables()
                    except: pass
                    RELOAD_UI = False
                    
                lbl_relogio.value = datetime.now().strftime("%H:%M:%S")
                lbl_btc_msg.value = f"BTC | {str(BTC_TREND.get('txt',''))}"
                lbl_btc_msg.color = str(BTC_TREND.get('cor','white'))
                texto_status = str(SCAN_STATE.get("status",""))
                lbl_scanning.value = texto_status
                
                if time.time() - ultimo_rest > 2.5:
                    try:
                        tickers = exchange.fetch_tickers()
                        for sym, data in tickers.items():
                            if sym.endswith('USDT') and data.get('last'):
                                s_clean = sym.split(':')[0].replace('/', '')
                                PRECOS_WS[s_clean] = float(data['last'])
                        ultimo_rest = time.time()
                    except: pass

                snap = PRECOS_WS.copy(); fechamentos_pendentes = [] 
                
                with ui_lock:
                    c_r, c_s, c_b, f_r, f_s, f_b = 0, 0, 0, 0.0, 0.0, 0.0
                    for t in CARTEIRA:
                        if type(t) is not dict: continue
                        est_tipo = t.get('est', 'UNK')
                        if est_tipo == 'REAL': c_r += 1
                        elif est_tipo == 'SIMU': c_s += 1
                        elif est_tipo == 'SIMU_B': c_b += 1
                        
                        px = snap.get(str(t.get('symbol','')).replace('/', '').replace(':USDT', ''))
                        entry_p = safe_float(t.get('entry'))
                        if entry_p <= 0: entry_p = 1.0 
                        
                        if px:
                            diff = (px - entry_p) if t.get('side') == 'LONG' else (entry_p - px)
                            t['roi'], t['now'] = (diff / entry_p) * safe_float(t.get('lev', 20.0)) * 100, px
                            t['pnl'] = (safe_float(t.get('margin')) * safe_float(t.get('roi'))) / 100
                            t['max'] = max(safe_float(t.get('max')), safe_float(t.get('roi')))
                            t['min'] = min(safe_float(t.get('min')), safe_float(t.get('roi')))
                            
                            if est_tipo == 'REAL': f_r += safe_float(t.get('pnl'))
                            elif est_tipo == 'SIMU': f_s += safe_float(t.get('pnl'))
                            elif est_tipo == 'SIMU_B': f_b += safe_float(t.get('pnl'))
                            
                            chave = str(t.get('id', ''))
                            if chave in UI_TRADES:
                                UI_TRADES[chave]['roi'].value = f"{safe_float(t.get('roi')):.2f}%"
                                UI_TRADES[chave]['roi'].color = (NEON_GREEN if safe_float(t.get('roi')) >= 0 else NEON_RED)
                                UI_TRADES[chave]['pnl'].value = f"${safe_float(t.get('pnl')):.2f}"
                                UI_TRADES[chave]['maxmin'].value = f"{safe_float(t.get('min')):.1f}% / {safe_float(t.get('max')):.1f}%"
                                
                                est_strategy = t.get('estrategia', 'A')
                                if est_strategy == 'B':
                                    if safe_float(t.get('roi')) >= 50: st_txt, st_cor = f"[B] 🏄 SURF MAX ({safe_float(t.get('stop_p')):.0f}%)", GOLD_TERTIARY
                                    elif safe_float(t.get('roi')) >= 20: st_txt, st_cor = f"[B] 🏄 SURF MIN ({safe_float(t.get('stop_p')):.0f}%)", GOLD_TERTIARY
                                    elif t.get('fez_parcial'): st_txt, st_cor = f"[B] 🛡️ PARCIAL FEITA ({safe_float(t.get('stop_p')):.0f}%)", GOLD_TERTIARY
                                    elif safe_float(t.get('roi')) >= 0: st_txt, st_cor = "[B] 🟢 BUSCANDO 15%", NEON_GREEN
                                    else: st_txt, st_cor = "[B] 🔴 ABERTA", NEON_RED
                                else:
                                    if safe_float(t.get('roi')) >= 100: st_txt, st_cor = f"[A] 🏄 SURF ({safe_float(t.get('stop_p')):.0f}%)", GOLD_SECONDARY
                                    elif safe_float(t.get('roi')) >= 0: st_txt, st_cor = "[A] 🟢 BUSCANDO 100%", NEON_GREEN
                                    else: st_txt, st_cor = "[A] 🔴 ABERTA", NEON_RED
                                    
                                UI_TRADES[chave]['status'].value = st_txt; UI_TRADES[chave]['status'].color = st_cor
                                try: UI_TRADES[chave]['roi'].update(); UI_TRADES[chave]['pnl'].update(); UI_TRADES[chave]['maxmin'].update(); UI_TRADES[chave]['status'].update()
                                except: pass
                                
                        if safe_float(t.get('roi')) <= safe_float(t.get('stop_p', STOP_LOSS_FIXO)): fechamentos_pendentes.append((t.get('id'), "AUTO-STOP / SURF SAÍDA"))

                for tid, motivo in fechamentos_pendentes:
                    try: encerrar_posicao_interface(tid, motivo)
                    except: pass

                for s in SINAIS_RECEBIDOS:
                    chave_s = f"{str(s.get('hora','-'))}_{str(s.get('moeda','-'))}_{str(s.get('tf','-'))}"
                    px_atual = snap.get(f"{str(s.get('moeda','-'))}USDT", safe_float(s.get('preco_in', 1.0)))
                    preco_in_s = safe_float(s.get('preco_in', 0))
                    
                    if preco_in_s > 0:
                        diff_s = (px_atual - preco_in_s) if "LONG" in str(s.get('lado','')) else (preco_in_s - px_atual)
                        pnl_s_vivo = (diff_s / preco_in_s) * ALAVANCAGEM_GLOBAL * 100
                    else: pnl_s_vivo = 0.0
                    
                    if chave_s in UI_SINAIS:
                        UI_SINAIS[chave_s]['now'].value = f"NOW: ${px_atual:.4f}"
                        UI_SINAIS[chave_s]['pnl'].value = f"{pnl_s_vivo:+.2f}%"
                        UI_SINAIS[chave_s]['pnl'].color = NEON_GREEN if pnl_s_vivo >= 0 else NEON_RED
                        try: UI_SINAIS[chave_s]['now'].update(); UI_SINAIS[chave_s]['pnl'].update()
                        except: pass

                try:
                    l_real = sum([safe_float(h.get('pnl')) for h in HISTORICO if type(h) is dict and h.get('est') == 'REAL'])
                    l_simu = sum([safe_float(h.get('pnl')) for h in HISTORICO if type(h) is dict and h.get('est') == 'SIMU'])
                    l_simu_b = sum([safe_float(h.get('pnl')) for h in HISTORICO if type(h) is dict and h.get('est') == 'SIMU_B'])
                    
                    if BANCA_REAL is not None: lbl_banca.value = f"${BANCA_REAL:.2f}"; lbl_banca.color = "white"; lbl_banca.size = 36
                    else:
                        if ERRO_BANCA: lbl_banca.value = f"⚠️ ERRO API: {ERRO_BANCA}"; lbl_banca.color = NEON_RED; lbl_banca.size = 18
                        else: lbl_banca.value = "Conectando API..."; lbl_banca.color = "white54"; lbl_banca.size = 36
                        
                    lbl_pnl_total_real.value, lbl_pnl_total_real.color = f"${l_real:+.2f}", (NEON_GREEN if l_real >= 0 else NEON_RED)
                    lbl_pnl_total_simu.value, lbl_pnl_total_simu.color = f"${l_simu:+.2f}", (NEON_GREEN if l_simu >= 0 else NEON_RED)
                    lbl_pnl_total_simu_b.value, lbl_pnl_total_simu_b.color = f"${l_simu_b:+.2f}", (NEON_GREEN if l_simu_b >= 0 else NEON_RED)
                    
                    try:
                        tr_w, tr_l = int(STATS['real']['w']), int(STATS['real']['l'])
                        ts_w, ts_l = int(STATS['simu']['w']), int(STATS['simu']['l'])
                        tb_w, tb_l = int(STATS['simu_b']['w']), int(STATS['simu_b']['l'])
                    except: tr_w, tr_l, ts_w, ts_l, tb_w, tb_l = 0, 0, 0, 0, 0, 0
                        
                    tot_r = max(1, tr_w + tr_l); wr_r = (tr_w / tot_r * 100) if tot_r > 0 else 0.0
                    tot_s = max(1, ts_w + ts_l); wr_s = (ts_w / tot_s * 100) if tot_s > 0 else 0.0
                    tot_b = max(1, tb_w + tb_l); wr_b = (tb_w / tot_b * 100) if tot_b > 0 else 0.0
                    
                    f_r_display = abs(f_r) if round(f_r, 2) == 0 else f_r
                    f_s_display = abs(f_s) if round(f_s, 2) == 0 else f_s
                    f_b_display = abs(f_b) if round(f_b, 2) == 0 else f_b
                    
                    pl_w.value, pl_l.value, pl_wr.value = f"🏆 W: {tr_w}", f"💀 L: {tr_l}", f"🎯 WR: {wr_r:.1f}%"
                    pl_liq.value, pl_flu.value, pl_count.value = f"💰 LÍQUIDO: ${l_real:.2f}", f"🌊 FLUTUANTE: ${f_r_display:.2f}", f"ATIVAS: {c_r}"
                    
                    pl_s_w.value, pl_s_l.value, pl_s_wr.value = f"🏆 W: {ts_w}", f"💀 L: {ts_l}", f"🎯 WR: {wr_s:.1f}%"
                    pl_s_liq.value, pl_s_flu.value, pl_s_count.value = f"💰 LÍQUIDO: ${l_simu:.2f}", f"🌊 FLUTUANTE: ${f_s_display:.2f}", f"ATIVAS: {c_s}"

                    pl_b_w.value, pl_b_l.value, pl_b_wr.value = f"🏆 W: {tb_w}", f"💀 L: {tb_l}", f"🎯 WR: {wr_b:.1f}%"
                    pl_b_liq.value, pl_b_flu.value, pl_b_count.value = f"💰 LÍQUIDO: ${l_simu_b:.2f}", f"🌊 FLUTUANTE: ${f_b_display:.2f}", f"ATIVAS: {c_b}"
                    
                    def get_log_color(l):
                        if "🔴" in l: return NEON_RED
                        if "🟡" in l: return GOLD_PRIMARY 
                        if "✅" in l: return NEON_GREEN
                        if "SHORT" in l: return NEON_RED
                        if "📡" in l: return GOLD_SECONDARY
                        return "white54"
                        
                    list_logs_home.controls = [ft.Text(str(log), color=get_log_color(str(log)), weight="bold", size=13) for log in LOGS_SINAIS_LISTA[:100]]
                    
                    updates = [pl_w, pl_l, pl_wr, pl_liq, pl_flu, pl_count, pl_s_w, pl_s_l, pl_s_wr, pl_s_liq, pl_s_flu, pl_s_count, pl_b_w, pl_b_l, pl_b_wr, pl_b_liq, pl_b_flu, pl_b_count, lbl_pnl_total_real, lbl_pnl_total_simu, lbl_pnl_total_simu_b, lbl_banca]
                    for ctrl in updates:
                        if getattr(ctrl, 'page', None):
                            try: ctrl.update()
                            except: pass
                except: pass

                try: page.update()
                except: pass
                time.sleep(0.5) 
            except Exception as e: time.sleep(1)

    threading.Thread(target=manter_banca_real, daemon=True).start()
    threading.Thread(target=refresh, daemon=True).start()

def manter_top_moedas_volume():
    global MOEDAS_PARA_SCAN
    while True:
        try:
            tickers = exchange.fetch_tickers()
            liq = [(sym.split('/')[0], float(data['quoteVolume'])) for sym, data in tickers.items() if sym.endswith(':USDT') and data.get('quoteVolume')]
            liq = [m for m in liq if m[0] not in ['USDC', 'FDUSD', 'TUSD', 'BUSD'] and m[0].isalnum()]
            liq.sort(key=lambda x: x[1], reverse=True); top = [m[0] for m in liq[:240]]
            if len(top) >= 10: MOEDAS_PARA_SCAN = top
        except: pass
        time.sleep(1800)

if __name__ == "__main__":
    inicializar_csvs_auditoria()
    threading.Thread(target=motor_filtro_btc, daemon=True).start()
    threading.Thread(target=manter_top_moedas_volume, daemon=True).start()
    threading.Thread(target=motor_sinais_elite, daemon=True).start()
    threading.Thread(target=motor_gatilho_sniper, daemon=True).start()
    
    # Suprimir logs do Flask para não sujar o terminal rodando por baixo do Flet
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 5000, 'debug': False, 'use_reloader': False}, daemon=True).start()
    
    ft.app(target=main)
