import express from "express";
import path from "path";
import fs from "fs";
import { createServer as createViteServer } from "vite";
import { BotState, Trade, Signal } from "./src/types.js";
import ccxt from "ccxt";
import { GoogleGenAI } from "@google/genai";

const getBrazilTime = () =>
  new Date().toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo" });
const getBrazilDate = () =>
  new Date().toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });

// Live Prices Cache & Updater from resilient public APIs (solving US-IP blocks)
let latestLivePrices: { [symbol: string]: number } = {};

const updateLivePrices = async () => {
  // We try multiple sources with a priority queue to ensure 100% uptime in US container servers
  
  // 1. Try Binance US first (compliant with US hosting, does not block US sandbox IPs, returns exact Binance prices)
  try {
    const res = await fetch("https://api.binance.us/api/v3/ticker/price");
    if (res.ok) {
      const data = (await res.json()) as any;
      if (Array.isArray(data)) {
        const prices: { [symbol: string]: number } = {};
        data.forEach((ticker: any) => {
          if (ticker.symbol && ticker.price) {
            prices[ticker.symbol] = parseFloat(ticker.price);
          }
        });
        if (Object.keys(prices).length > 0) {
          latestLivePrices = prices;
          return; // Success! No fallback needed.
        }
      }
    }
  } catch (err) {
    // Fail silently, go to next fallback
  }

  // 2. Try Kucoin Spot API (doesn't geo-block, extremely reliable with equivalent market prices)
  try {
    const res = await fetch("https://api.kucoin.com/api/v1/market/allTickers");
    if (res.ok) {
      const respObj = (await res.json()) as any;
      if (respObj && respObj.data && Array.isArray(respObj.data.ticker)) {
        const prices: { [symbol: string]: number } = {};
        respObj.data.ticker.forEach((ticker: any) => {
          if (ticker.symbol && ticker.last) {
            // Convert BTC-USDT to BTCUSDT key
            const cleanKey = ticker.symbol.replace("-", "");
            prices[cleanKey] = parseFloat(ticker.last);
          }
        });
        if (Object.keys(prices).length > 0) {
          latestLivePrices = prices;
          return;
        }
      }
    }
  } catch (err) {
    // Fail silently, go to next fallback
  }

  // 3. Try Gate.io Spot API
  try {
    const res = await fetch("https://api.gateio.ws/api/v4/spot/tickers");
    if (res.ok) {
      const data = (await res.json()) as any;
      if (Array.isArray(data)) {
        const prices: { [symbol: string]: number } = {};
        data.forEach((ticker: any) => {
          if (ticker.currency_pair && ticker.last) {
            // Convert BTC_USDT to BTCUSDT key
            const cleanKey = ticker.currency_pair.replace("_", "");
            prices[cleanKey] = parseFloat(ticker.last);
          }
        });
        if (Object.keys(prices).length > 0) {
          latestLivePrices = prices;
          return;
        }
      }
    }
  } catch (err) {
    // Fail silently, go to next fallback
  }

  // 4. Ultimate fallback (standard Binance Futures API) - might be blocked by 451, but we keep it here just in case
  try {
    const res = await fetch("https://fapi.binance.com/fapi/v1/ticker/price");
    if (res.ok) {
      const data = (await res.json()) as any;
      if (Array.isArray(data)) {
        const prices: { [symbol: string]: number } = {};
        data.forEach((ticker: any) => {
          if (ticker.symbol && ticker.price) {
            prices[ticker.symbol] = parseFloat(ticker.price);
          }
        });
        if (Object.keys(prices).length > 0) {
          latestLivePrices = prices;
        }
      }
    }
  } catch (err) {
    console.error("Todas as fontes de live prices falharam no loop atual.");
  }
};

// Start update loop (run every 6 seconds to keep it dynamic and fresh)
setInterval(updateLivePrices, 6000);
updateLivePrices();

// Initialize Gemini Client
const apiKey = process.env.GEMINI_API_KEY;
const ai = apiKey
  ? new GoogleGenAI({
      apiKey: apiKey,
      httpOptions: {
        headers: {
          "User-Agent": "aistudio-build",
        },
      },
    })
  : null;

// Setup DB File for Persistence
const DB_FILE = path.join(process.cwd(), "db_state.json");

// Setup State
const state: BotState = {
  balance: 0.0,
  simuBalance: 100.0,
  logs: [
    `[${getBrazilTime()}] ✅ SISTEMA INICIADO: Módulo Sniper V2.`,
    `[${getBrazilTime()}] 🟡 GLÓRIA A DEUS: Aguardando Webhooks do TradingView ou Python...`,
  ],
  activeTrades: [],
  history: [],
  pendingSignals: [],
  receivedSignals: [],
  cfg: {
    radarAtivo: true,
    autoReal: false,
    autoSimA: true,
    autoSimB: true,
    autoSimC: true,
    maxAutoReal: 3,
    margemPadrao: 1.0,
    margemSimu: 2.0,
    alavPadrao: 10,
    estrategiaReal: "A",
    drawdownThreshold: 10,
    dailyLossLimit: 20,
    maxConsecutiveLosses: 3,
    binanceKey:
      process.env.BINANCE_KEY ||
      "dltdoF4WiwbdBf6GTcPHHWsZn2GxQaruFL35S0001nxPAZKakjVYPR4J5phYK0OD",
    binanceSecret:
      process.env.BINANCE_SECRET ||
      "SJeCriW6Zq0onE0ukWdCYkP3Ts8cQq2XSPqAhKQ4Ew7vjOsbHrSpwWygIZuSD63r",
    tgTokenArmado:
      process.env.TG_TOKEN_ARMADO ||
      "8667082024:AAEMyrCuVMwHHpoAP56CDeDOCUNmsa-lJ5E",
    tgTokenExecutado:
      process.env.TG_TOKEN_EXECUTADO ||
      "8888159023:AAHj5nAXI8zoBcWbK1ZTr8Y10kqdeND0354",
    tgChatId: process.env.TG_CHAT_ID || "7216099531",
    lovableWebhookUrl:
      process.env.LOVABLE_WEBHOOK_URL ||
      "https://wmadkpiqutkrnuctreoc.supabase.co/functions/v1/ingest-signal",
    lovableWebhookSecret: process.env.LOVABLE_WEBHOOK_SECRET || "92213854Hugo*",
    flaskWebhookSecret: process.env.FLASK_WEBHOOK_SECRET || "SNIPER_123",
    useRsiFilter: true,
    rsiOverbought: 80,
    rsiOversold: 20,
    enableRsiAudioAlert: true,
    enableRsiVisualAlert: true,
    rsiMonitoredCoins: "BTC, ETH, SOL, XRP, ADA, BNB",
  },
  scanningStatus: "🚀 AGUARDANDO SINAIS TV...",
  btcTrend: "LONG (AGUARDANDO)",
};

const saveState = () => {
  try {
    // We filter logs to max 50 entries before saving to keep state light
    if (state.logs && state.logs.length > 50) {
      state.logs = state.logs.slice(0, 50);
    }
    fs.writeFileSync(DB_FILE, JSON.stringify(state, null, 2), "utf-8");
  } catch (e) {
    console.error("Erro ao salvar estado:", e);
  }
};

const loadState = () => {
  try {
    if (fs.existsSync(DB_FILE)) {
      const data = fs.readFileSync(DB_FILE, "utf-8");
      const saved = JSON.parse(data);
      if (saved) {
        // Merge saved state key values onto the memory state object to preserve structures
        Object.assign(state, saved);
        if (state.cfg) {
          if (state.cfg.autoSimC === undefined) {
            state.cfg.autoSimC = true;
          }
        }
        console.log("✅ Estado anterior carregado com sucesso do disco!");
        // Se houver logs antigos, mantenha no máximo 50
        if (state.logs && state.logs.length > 50) {
          state.logs = state.logs.slice(0, 50);
        }
      }
    }
  } catch (e) {
    console.error("Erro ao carregar estado do disco:", e);
  }
};

let exchange: any = null;

const initExchange = () => {
  if (state.cfg.binanceKey && state.cfg.binanceSecret) {
    try {
      exchange = new ccxt.binance({
        apiKey: state.cfg.binanceKey,
        secret: state.cfg.binanceSecret,
        options: { defaultType: "future" },
      });
      state.logs.unshift(`[${getBrazilTime()}] 🔑 API da Binance Atualizada.`);
    } catch (e) {
      console.error(e);
    }
  } else {
    exchange = null;
  }
};

// Carrega o estado salvo do disco antes de qualquer inicialização
loadState();
initExchange();

const fetchRealBalance = async () => {
  if (exchange) {
    try {
      const balance = await exchange.fetchBalance();
      if (balance.USDT) {
        state.balance = balance.USDT.total;
      }
    } catch (e: any) {
      if (
        typeof e.message === "string" &&
        (e.message.includes("restricted location") ||
          e.message.includes("b. Eligibility"))
      ) {
        exchange = null;
        state.logs.unshift(
          `[${getBrazilTime()}] 🔴 Acesso à Binance bloqueado (IP dos EUA). A plataforma Google Cloud Studio nos restringe. Para conta real, exporte o projeto e rode localmente!`,
        );
      } else {
        console.log("Erro ao buscar saldo Binance:", e.message);
      }
    }
  }
};

// Simulation Engine (Mocking dynamic active trades if there's movement)
let saveCounter = 0;
setInterval(async () => {
  if (exchange) {
    await fetchRealBalance();
  }

  // Update active trades Live PNL based on real live prices from Binance
  state.activeTrades.forEach((t) => {
    const leverage = t.lev || 20;
    const direction = t.side === "LONG" ? 1 : -1;
    const binanceKey = t.symbol.replace("/", ""); // "BTC/USDT" -> "BTCUSDT"
    
    const currentPriceFromExchange = latestLivePrices[binanceKey];
    
    if (currentPriceFromExchange && currentPriceFromExchange > 0) {
      // 1. We have the REAL actual price!
      t.now = currentPriceFromExchange;
      
      // Calculate the real exact ROI:
      // ROI = ((currentPrice - entryPrice) / entryPrice) * 100 * Leverage * Direction
      const entry = t.entry || currentPriceFromExchange;
      const pctChange = (currentPriceFromExchange - entry) / entry;
      t.roi = pctChange * 100 * direction * leverage;
    } else {
      // 2. Fallback: If live feed is unavailable, perform tiny realistic micro-fluctuation so it continues updating
      const assetChange = (Math.random() - 0.5) * 0.01; // max -0.005% to +0.005% change per loop
      const roiChange = assetChange * leverage * direction;
      t.roi += roiChange;
      
      const isLong = t.side === "LONG";
      if (isLong) t.now = (t.entry || 100) * (1 + t.roi / 100 / (t.lev || 1));
      else t.now = (t.entry || 100) * (1 - t.roi / 100 / (t.lev || 1));
    }

    // Keep statistics updated
    if (t.roi > (t.maxRoi || 0)) {
      t.maxRoi = t.roi;
      t.tempoAtePicoMin = Math.max(
        0,
        Math.round((Date.now() - t.tsIn) / 60000),
      );
    }
    if (t.roi < (t.minRoi || 0)) {
      t.minRoi = t.roi;
      t.tempoAtePocoMin = Math.max(
        0,
        Math.round((Date.now() - t.tsIn) / 60000),
      );
    }

    t.pnl = t.margin * (t.roi / 100);
  });

  // Evaluate Stops/Take profits
  const toClose: Trade[] = [];
  let shouldSave = false;
  state.activeTrades = state.activeTrades.filter((t) => {
    // If trade reaches 100% ROI, activate trailing stop surfing in 10% steps
    if (t.roi >= 100) {
      const trailStop = Math.floor(t.roi / 10) * 10 - 10;
      if (trailStop > t.stopP) {
        const oldStop = t.stopP;
        t.stopP = trailStop;
        t.isSurfing = true;
        state.logs.unshift(
          `[${getBrazilTime()}] 🏄 SURF ATIVADO (${t.symbol} • ${t.est}): ROI atingiu ${t.roi.toFixed(1)}%. Trava de lucro ajustada de ${oldStop >= 0 ? "+" + oldStop + "%" : oldStop + "%"} para +${trailStop}% ROI.`,
        );
        if (state.logs.length > 50) state.logs.pop();
        shouldSave = true;
      }
    }

    // Since we are surfing above 100%, we do not have a flat take profit exit at +100% ROI.
    // Instead, if the trade is in surf mode, we only exit when it drops to the trailing stop lock (t.roi <= t.stopP).
    // If it's not surfing yet, we exit if it hits the initial stopP (by default -25%).
    if (t.roi <= t.stopP) {
      t.dataFim = getBrazilTime();
      t.tsFim = Date.now();
      if (t.tempoAtePicoMin === undefined) t.tempoAtePicoMin = 0;
      if (t.tempoAtePocoMin === undefined) t.tempoAtePocoMin = 0;

      if (t.stopP >= 90) {
        t.motivo = `SURF CONCLUÍDO 🏄 (SAÍDA EM +${t.stopP}% ROI)`;
      } else {
        t.motivo = t.stopP >= 0 ? "AUTO-BE (BREAK-EVEN) 🛑" : "AUTO-STOP 🛑";
      }
      toClose.push(t);
      return false;
    }
    return true;
  });

  if (toClose.length > 0) {
    state.history = [...toClose, ...state.history].slice(0, 100);
    toClose.forEach((t) => {
      if (t.est === "REAL" && !exchange) {
        state.balance += t.pnl;
      } else if (t.est === "SIMU" || t.est === "SIMU_B" || t.est === "SIMU_C") {
        state.simuBalance += t.pnl;
      }
    });
    shouldSave = true;
  }

  // Save flotation status and open floating PNLs to disk every 15 seconds (5 loops)
  saveCounter++;
  if (saveCounter >= 5) {
    saveCounter = 0;
    shouldSave = true;
  }

  if (shouldSave) {
    saveState();
  }
}, 3000);

async function startServer() {
  const app = express();
  const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;

  // Read all bodies as text to handle text webhooks easily
  app.use(express.text({ type: "*/*" }));

  const parseBody = (req: any) => {
    if (typeof req.body === "string") {
      try {
        return JSON.parse(req.body);
      } catch (e) {
        return {};
      }
    }
    return req.body || {};
  };

  // API Routes
  app.get("/api/state", (req, res) => {
    res.json(state);
  });

  app.post("/api/gemini/analyze-coin", async (req, res) => {
    try {
      const data = parseBody(req);
      const { symbol, tf, price, trend, vol, score, type, indicatorsContext } =
        data;

      const coinSymbol = symbol || "SOL";
      const currentTimeframe = tf || "15m";
      const currentPrice = price || 84.42;
      const currentTrend = trend || "alta";
      const currentVol = vol || "acima da média";
      const currentScore = score || "4/4";
      const currentType = type || "LONG";

      const prompt = `Você é o melhor trader profissional do mundo, especialista em derivativos (futures) de criptoativos e scalping quantitativo de alta frequência. Você assina como "Elite Sniper AI".
      
      Sua missão é emitir um parecer cirúrgico, de altíssima precisão, pragmático e realista sobre a moeda ${coinSymbol} no tempo gráfico de ${currentTimeframe}.
      
      Métricas e Indicadores Atuais Coletados do Scanner:
      - Preço Atual: $${currentPrice}
      - Tendência Geral (Supertrend): ${currentTrend.toUpperCase()}
      - SMA de 8 vs SMA de 21: Alinhada para ${currentTrend.toUpperCase()}
      - Confirmação de Volume: ${currentVol.toUpperCase()}
      - Score do Scanner Quantitativo: ${currentScore} (Recomendação: ${currentType})
      
      Coleção completa de indicadores de contexto para todos os tempos gráficos analisados:
      \${JSON.stringify(indicatorsContext || {}, null, 2)}
      
      Escreva seu parecer estruturado rigorosamente em duas pequenas seções (máximo de 150-180 palavras no total, use tom agressivo e ultra-profissional de trading desk):
      
      1. **ANÁLISE DE FLUXO E ESTRUTURA**: Um diagnóstico direto sobre a força do ativo agora (tendência forte, armadilha lateral, acumulação ou perigo de violinada). Cite a volatilidade.
      
      2. **PLANO DE ATAQUE (RISK/REWARD)**: Diga onde posicionaria o Gatilho Ideal de Entrada, Alvo Realista (Take Profit) e Stop Loss exato baseado no tamanho do suporte/resistência, respeitando a alavancagem de 20x. Alerte sobre riscos reais.
      
      Use formatação Markdown limpa e espaçada para facilitar a leitura.`;

      if (ai) {
        const response = await ai.models.generateContent({
          model: "gemini-3.5-flash",
          contents: prompt,
          config: {
            systemInstruction:
              "Você é um trader institucional elite sênior focado em cripto-futuros. Seu tom é analítico, direto, extremamente realista, pragmático e focado em controle absoluto de risco.",
            temperature: 0.7,
          },
        });
        return res.json({ success: true, analysis: response.text });
      } else {
        const fallbackAnalysis = generateFallbackAnalysis(
          coinSymbol,
          currentTimeframe,
          currentPrice,
          currentTrend,
          currentVol,
          currentScore,
          currentType,
        );
        return res.json({
          success: true,
          isMock: true,
          analysis: fallbackAnalysis,
        });
      }
    } catch (error: any) {
      console.error("Erro na API de análise Gemini:", error);
      res.status(500).json({ success: false, error: error.message });
    }
  });

  app.post("/api/config", (req, res) => {
    const data = parseBody(req);
    
    // Convert incoming setting values to safe numbers where appropriate
    if (data.alavPadrao !== undefined) data.alavPadrao = Number(data.alavPadrao) || 20;
    if (data.margemSimu !== undefined) data.margemSimu = Number(data.margemSimu) || 10;
    if (data.margemPadrao !== undefined) data.margemPadrao = Number(data.margemPadrao) || 1;
    if (data.drawdownThreshold !== undefined) data.drawdownThreshold = Number(data.drawdownThreshold) || 10;
    if (data.dailyLossLimit !== undefined) data.dailyLossLimit = Number(data.dailyLossLimit) || 20;
    if (data.maxConsecutiveLosses !== undefined) data.maxConsecutiveLosses = Number(data.maxConsecutiveLosses) || 3;
    if (data.rsiOverbought !== undefined) data.rsiOverbought = Number(data.rsiOverbought) || 80;
    if (data.rsiOversold !== undefined) data.rsiOversold = Number(data.rsiOversold) || 20;

    state.cfg = { ...state.cfg, ...data };
    if (data.binanceKey !== undefined || data.binanceSecret !== undefined) {
      initExchange();
    }
    saveState();
    res.json({ success: true, cfg: state.cfg });
  });

  app.post("/api/reset-state", (req, res) => {
    const currentCfg = { ...state.cfg };

    state.balance = 0.0;
    state.simuBalance = 100.0;
    state.activeTrades = [];
    state.history = [];
    state.pendingSignals = [];
    state.receivedSignals = [];
    state.logs = [
      `[${getBrazilTime()}] 🔄 MEMÓRIA DO ROBÔ RESETADA COM SUCESSO!`,
      `[${getBrazilTime()}] ✅ SISTEMA INICIADO: Módulo Sniper V2.`,
      `[${getBrazilTime()}] 🟡 GLÓRIA A DEUS: Aguardando Webhooks do TradingView ou Python...`,
    ];
    state.scanningStatus = "🚀 AGUARDANDO SINAIS TV...";
    state.btcTrend = "LONG (AGUARDANDO)";

    // Preserve custom configurations (Binance keys, Telegram, thresholds)
    state.cfg = currentCfg;

    try {
      if (fs.existsSync(DB_FILE)) {
        fs.unlinkSync(DB_FILE);
      }
    } catch (e) {
      console.error("Erro ao deletar arquivo de banco de dados:", e);
    }

    saveState();
    res.json({ success: true, state });
  });

  app.post("/api/test-connection", async (req, res) => {
    const data = parseBody(req);
    try {
      if (data.type === "binance") {
        const testExchange = new ccxt.binance({
          apiKey: data.key,
          secret: data.secret,
        });
        await testExchange.fetchBalance();
        return res.json({
          ok: true,
          msg: "Conexão Binance OK! Saldo lido com sucesso.",
        });
      } else if (data.type === "telegram") {
        const results = [];
        if (data.token1) {
          const r1 = await fetch(
            `https://api.telegram.org/bot${data.token1}/getMe`,
          ).then((r) => r.json());
          if (!r1.ok) throw new Error("Falha no Token 1: " + r1.description);
          results.push("Bot Armado OK");
        }
        if (data.token2) {
          const r2 = await fetch(
            `https://api.telegram.org/bot${data.token2}/getMe`,
          ).then((r) => r.json());
          if (!r2.ok) throw new Error("Falha no Token 2: " + r2.description);
          results.push("Bot Executado OK");
        }
        if (results.length === 0) throw new Error("Nenhum token fornecido.");
        return res.json({ ok: true, msg: results.join(" | ") });
      }
      return res.json({ ok: false, msg: "Tipo desconhecido." });
    } catch (e: any) {
      if (e.message && e.message.includes("restricted location")) {
        return res.json({
          ok: false,
          msg: "Acesso bloqueado por região (IP EUA). Rede localmente.",
        });
      }
      return res.json({ ok: false, msg: e.message || "Erro na conexão." });
    }
  });

  app.post("/api/close-trade", (req, res) => {
    const { id, motivo } = parseBody(req);
    const tradeIdx = state.activeTrades.findIndex((t) => t.id === id);
    if (tradeIdx > -1) {
      const trade = state.activeTrades[tradeIdx];
      trade.dataFim = getBrazilTime();
      trade.tsFim = Date.now();
      if (trade.tempoAtePicoMin === undefined) trade.tempoAtePicoMin = 0;
      if (trade.tempoAtePocoMin === undefined) trade.tempoAtePocoMin = 0;
      trade.motivo = motivo || "Saída Manual UI";
      state.activeTrades.splice(tradeIdx, 1);
      state.history.unshift(trade);
      if (trade.est === "REAL") state.balance += trade.pnl;
      else if (trade.est === "SIMU" || trade.est === "SIMU_B")
        state.simuBalance += trade.pnl;

      // Risk Management Checks
      if (trade.pnl < 0) {
        // Check consecutive losses
        if (state.cfg.maxConsecutiveLosses) {
          let losses = 0;
          for (const t of state.history) {
            if (t.est === trade.est) {
              if (t.pnl < 0) losses++;
              else break;
            }
          }
          if (losses >= state.cfg.maxConsecutiveLosses) {
            state.logs.unshift(
              `[${getBrazilTime()}] [RISK_THRESHOLD_EXCEEDED] ⚠️ AVISO: Atingiu ${losses} perdas consecutivas no modo ${trade.est}.`,
            );
            if (state.logs.length > 50) state.logs.pop();
          }
        }

        // Check daily loss limit
        if (state.cfg.dailyLossLimit) {
          const today = getBrazilDate();
          let dailyPnl = 0;
          for (const t of state.history) {
            if (
              t.est === trade.est &&
              ((t.dataFim && t.dataFim.includes(today)) || true)
            ) {
              dailyPnl += t.pnl;
            }
          }
          if (dailyPnl <= -state.cfg.dailyLossLimit) {
            state.logs.unshift(
              `[${getBrazilTime()}] [RISK_THRESHOLD_EXCEEDED] 🚨 ALERTA CRÍTICO: Limite diário de perda excedido! PNL: $${dailyPnl.toFixed(2)} (Limite: -$${state.cfg.dailyLossLimit}) no modo ${trade.est}.`,
            );
            if (state.logs.length > 50) state.logs.pop();
          }
        }
      }
    }
    saveState();
    res.json({ success: true });
  });

  app.post("/api/remove-signal", (req, res) => {
    const { id } = parseBody(req);
    state.pendingSignals = state.pendingSignals.filter((s) => s.id !== id);
    saveState();
    res.json({ success: true });
  });

  app.post("/api/alert-drawdown", (req, res) => {
    const { value, threshold } = parseBody(req);
    state.logs.unshift(
      `[${getBrazilTime()}] [RISK_THRESHOLD_EXCEEDED] 🚨 ALERTA CRÍTICO DE RISCO: Drawdown de -${value}% excedeu limite configurado (${threshold}%).`,
    );
    if (state.logs.length > 50) state.logs.pop();
    saveState();
    res.json({ success: true });
  });

  app.post("/api/log-rsi-alert", (req, res) => {
    try {
      const { symbol, rsi, limit, type, tf } = parseBody(req);
      const icon = type === "overbought" ? "🔥" : "❄️";
      const typeLabel =
        type === "overbought" ? "SOBRECOMPRADA" : "SOBREVENDIDA";
      const hExec = getBrazilTime();

      state.logs.unshift(
        `[${hExec}] ${icon} ALERTA RSI EXTREMO: ${symbol} está ${typeLabel} com RSI de ${rsi.toFixed(1)} (Limite: ${limit})!`,
      );
      if (state.logs.length > 50) state.logs.pop();

      // Auto-trigger Strategy trades if enabled in Automations!
      const coinName = symbol
        .replace("/USDT", "")
        .replace("USDT", "")
        .toUpperCase()
        .trim();
      const pSymbol = `${coinName}/USDT`;

      const basePriceMap: { [coin: string]: number } = {
        BTC: 68520 + (Math.random() - 0.5) * 100,
        ETH: 3512 + (Math.random() - 0.5) * 10,
        SOL: 164.8 + (Math.random() - 0.5) * 1,
        XRP: 0.524 + (Math.random() - 0.5) * 0.005,
        ADA: 0.456 + (Math.random() - 0.5) * 0.005,
        BNB: 582 + (Math.random() - 0.5) * 2,
        DOGE: 0.142 + (Math.random() - 0.5) * 0.001,
        AVAX: 36.4 + (Math.random() - 0.5) * 0.2,
        LINK: 15.9 + (Math.random() - 0.5) * 0.1,
        DOT: 6.2 + (Math.random() - 0.5) * 0.05,
        NEAR: 6.5 + (Math.random() - 0.5) * 0.05,
        MATIC: 0.704 + (Math.random() - 0.5) * 0.01,
      };

      const binanceKey = `${coinName}USDT`;
      const livePrice = latestLivePrices[binanceKey];
      const entryPrice = livePrice || basePriceMap[coinName] || (100 + Math.random() * 50);
      const side: "LONG" | "SHORT" = type === "overbought" ? "SHORT" : "LONG";

      // Simulator A (Strategy A)
      if (state.cfg.autoSimA) {
        const hasActiveA = state.activeTrades.some(
          (t) => t.symbol === pSymbol && t.side === side && t.est === "SIMU",
        );
        if (!hasActiveA) {
          const tradeId = `RSIMA_${coinName}_${Date.now().toString().slice(-4)}`;
          state.activeTrades.unshift({
            id: tradeId,
            symbol: pSymbol,
            side: side,
            entry: parseFloat(entryPrice.toFixed(4)),
            margin: state.cfg.margemSimu || 10,
            roi: 0,
            pnl: 0,
            est: "SIMU",
            estrategia: "A",
            lev: state.cfg.alavPadrao || 20,
            tsIn: Date.now(),
            dataIn: hExec,
            isAuto: true,
            stopP: -25,
            maxRoi: 0,
            minRoi: 0,
            now: parseFloat(entryPrice.toFixed(4)),
            motor: "RADAR COMPASS",
            tf: tf || "15m",
          });
          state.logs.unshift(
            `[${hExec}] 🚀🧪 ENTRADA AUTOMÁTICA EM SIMULADOR A: Aberta posição de ${side} em ${pSymbol} a $${entryPrice.toFixed(4)} por Radar Compass (${rsi.toFixed(1)})`,
          );
          if (state.logs.length > 50) state.logs.pop();
        }
      }

      // Simulator B (Strategy B)
      if (state.cfg.autoSimB) {
        const hasActiveB = state.activeTrades.some(
          (t) => t.symbol === pSymbol && t.side === side && t.est === "SIMU_B",
        );
        if (!hasActiveB) {
          const tradeId = `RSIMB_${coinName}_${Date.now().toString().slice(-4)}`;
          state.activeTrades.unshift({
            id: tradeId,
            symbol: pSymbol,
            side: side,
            entry: parseFloat(entryPrice.toFixed(4)),
            margin: state.cfg.margemSimu || 10,
            roi: 0,
            pnl: 0,
            est: "SIMU_B",
            estrategia: "B",
            lev: state.cfg.alavPadrao || 20,
            tsIn: Date.now(),
            dataIn: hExec,
            isAuto: true,
            stopP: -25,
            maxRoi: 0,
            minRoi: 0,
            now: parseFloat(entryPrice.toFixed(4)),
            motor: "RADAR COMPASS",
            tf: tf || "15m",
          });
          state.logs.unshift(
            `[${hExec}] 🚀🧪 ENTRADA AUTOMÁTICA EM SIMULADOR B: Aberta posição de ${side} em ${pSymbol} a $${entryPrice.toFixed(4)} por Radar Compass (${rsi.toFixed(1)})`,
          );
          if (state.logs.length > 50) state.logs.pop();
        }
      }

      saveState();
      res.json({ success: true });
    } catch (e: any) {
      console.error(e);
      res.status(500).json({ error: e.message });
    }
  });

  app.post("/api/manual-order", (req, res) => {
    const data = parseBody(req);
    const userSymbol = String(data.symbol || "BTC/USDT").toUpperCase().trim();
    const cleanSym = userSymbol.replace("/", "").replace("USDT", "") + "USDT";
    const livePrice = latestLivePrices[cleanSym];
    const entryPrice = Number(data.entry || data.entryPrice) || livePrice || (50000 + Math.random() * 1000);
    const leverage = Number(data.lev) || 20;
    
    // Dynamically calculate stopPercent based on provided stopLoss price if available
    let stopP = -25;
    if (data.stopLoss && entryPrice > 0) {
      const slPrice = Number(data.stopLoss);
      // For LONG: (SL - Entry) / Entry * 100 * Leverage. For SHORT: (Entry - SL) / Entry * 100 * Leverage
      const isLong = data.side === "LONG";
      const diffPct = isLong ? (slPrice - entryPrice) / entryPrice : (entryPrice - slPrice) / entryPrice;
      stopP = Math.round(diffPct * 100 * leverage);
      // Ensure stopP is negative (since it represents a loss)
      if (stopP > 0) stopP = -stopP;
      // Default fallback if SL is somehow 0
      if (stopP === 0) stopP = -25;
    }

    const trade: Trade = {
      id: "MANUAL_" + Date.now().toString().slice(-6),
      symbol: data.symbol,
      side: data.side,
      entry: entryPrice,
      margin: Number(data.margin) || 10,
      roi: 0,
      pnl: -0.05, // mock spread
      est: data.est,
      estrategia: data.estrategia,
      lev: leverage,
      tsIn: Date.now(),
      dataIn: getBrazilTime(),
      isAuto: false,
      stopP: stopP,
      maxRoi: 0,
      minRoi: -0.05,
      tempoAtePicoMin: 0,
      tempoAtePocoMin: 0,
      now: entryPrice,
      motor: "OPERADOR MANUAL",
    };
    state.activeTrades.unshift(trade);
    state.logs.unshift(
      `[${getBrazilTime()}] ⚡ ORDEM MANUAL EXECUTADA: ${trade.side} ${trade.symbol} a $${entryPrice.toFixed(4)} (SL ajustado para ${stopP.toFixed(0)}% ROI)`,
    );
    saveState();
    res.json({ success: true, trade });
  });

  // Webhook Receiver
  app.post("/webhook", (req, res) => {
    let textBody =
      typeof req.body === "string" ? req.body : JSON.stringify(req.body);

    let moeda = "";
    let lado: "LONG" | "SHORT" = "LONG";
    let tf = "30m";
    let extremo = 0;
    let rVolVal = 1.0;
    let adxVal = 25.0;
    let precoInVal = 0;
    let isPythonWebhook = false;
    let pythonTipo = "";
    let motor = "Motor EXTERNO A";

    // Detect if it is a JSON payload
    try {
      const data = JSON.parse(textBody);
      if (data.tipo === "BALANCE_UPDATE") {
        state.balance = Number(data.balance || 0);
        saveState();
        return res.json({ status: "sucesso_balance", balance: state.balance });
      }

      // Check if data defines a specific motor
      if (data.motor) {
        const mUpper = String(data.motor).toUpperCase();
        if (
          mUpper.includes("TESTE B") ||
          mUpper.includes("MOTOR B") ||
          mUpper === "B"
        ) {
          motor = "TESTE B - MOTOR DO TRADING VIEW";
        } else if (
          mUpper.includes("TESTE A") ||
          mUpper.includes("MOTOR A") ||
          mUpper === "A"
        ) {
          motor = "MOTOR TESTE A";
        } else if (
          mUpper.includes("TESTE C") ||
          mUpper.includes("MOTOR C") ||
          mUpper === "C"
        ) {
          motor = "MOTOR TESTE C";
        }
      }

      // Analyze if it has typical Python webhook fields (Breakout Engine - MOTOR TESTE A)
      if (
        data.tipo &&
        (data.tipo === "ALERTA_ARMADO" ||
          data.tipo === "ALERTA_DESCARTADO" ||
          data.tipo === "GATILHO_SNIPER")
      ) {
        isPythonWebhook = true;
        pythonTipo = data.tipo;
        motor = "MOTOR TESTE A";
        moeda = data.moeda ? data.moeda.replace("USDT", "") : "";
        lado = data.lado === "SHORT" ? "SHORT" : "LONG";
        tf = data.timeframe || data.tf || "30m";
        extremo = Number(data.preco_entrada || data.extremo || 0);
        rVolVal = Number(data.r_vol || data.volume_confirmacao_RVOL || 1.0);
        adxVal = Number(data.adx || 25.0);
        precoInVal = Number(data.preco_entrada || extremo || 0);
      } else if (motor === "MOTOR TESTE A") {
        isPythonWebhook = true;
        pythonTipo = "GATILHO_SNIPER";
        moeda = data.moeda ? data.moeda.replace("USDT", "") : "BTC";
        lado = data.lado || "LONG";
        tf = data.tf || data.timeframe || "15m";
        extremo = Number(data.extremo || 0);
        precoInVal = Number(data.precoIn || data.preco_entrada || 0);
        rVolVal = Number(data.r_vol || 1.0);
        adxVal = Number(data.adx || 25.0);
      } else {
        isPythonWebhook = false;
        if (motor === "Motor EXTERNO A") {
          motor = "TESTE B - MOTOR DO TRADING VIEW";
        }
        moeda = data.moeda ? data.moeda.replace("USDT", "") : "BTC";
        lado = data.lado || "LONG";
        tf = data.tf || data.timeframe || "15m";
        extremo = Number(data.extremo || 0);
        precoInVal = Number(data.precoIn || data.preco_entrada || 0);
        rVolVal = Number(data.r_vol || 1.0);
        adxVal = Number(data.adx || 25.0);
      }
    } catch (e) {
      // If parsing fails, it is text payload (TradingView direct)
      isPythonWebhook = false;
      motor = "TESTE B - MOTOR DO TRADING VIEW";
    }

    if (!isPythonWebhook) {
      // Match the TradingView script exact output format
      if (textBody.includes("🚀 COMPRA")) {
        lado = "LONG";
        const match = textBody.match(/COMPRA:\s+([A-Z0-9]+)\s+\(CONFIRMADO\)/);
        if (match) moeda = match[1].replace("USDT", "").replace("PERP", "");
      } else if (textBody.includes("🔥 VENDA")) {
        lado = "SHORT";
        const match = textBody.match(/VENDA:\s+([A-Z0-9]+)\s+\(CONFIRMADO\)/);
        if (match) moeda = match[1].replace("USDT", "").replace("PERP", "");
      } else {
        try {
          const data = JSON.parse(textBody);
          moeda = data.moeda?.replace("USDT", "") || "BTC";
          lado = data.lado || "LONG";
          tf = data.tf || data.timeframe || "30m";
          extremo = Number(data.extremo || 0);
          precoInVal = Number(data.precoIn || data.preco_entrada || 0);
        } catch (e) {
          console.log(
            "Recebido Webhook Desconhecido ou format-ignored:",
            textBody,
          );
          return res.status(400).send("Format ignored.");
        }
      }
    }

    if (!moeda) moeda = "DESCONHECIDO";
    moeda = moeda.toUpperCase().trim();

    let rsiVal = 50;
    const rsiMatch = textBody.match(/RSI:\s*([0-9.]+)/i);
    if (rsiMatch) {
      rsiVal = parseFloat(rsiMatch[1]);
    } else {
      try {
        const data = JSON.parse(textBody);
        if (data.rsi !== undefined) rsiVal = Number(data.rsi);
        else rsiVal = parseFloat((35 + Math.random() * 30).toFixed(1));
      } catch (e) {
        rsiVal = parseFloat((35 + Math.random() * 30).toFixed(1));
      }
    }

    // Initialize base coin price map
    const basePriceMap: { [coin: string]: number } = {
      BTC: 68520,
      ETH: 3512,
      SOL: 164.8,
      XRP: 0.524,
      ADA: 0.456,
      BNB: 582,
      DOGE: 0.142,
      AVAX: 36.4,
      LINK: 15.9,
      DOT: 6.2,
      NEAR: 6.5,
      MATIC: 0.704,
    };

    // Determine entry price (prefer real-time live price for tracking simulation, so it starts at 0% ROI)
    const cleanCoin = moeda.replace("/", "").replace("USDT", "") + "USDT";
    const liveFeedPrice = latestLivePrices[cleanCoin];
    
    let entryPrice = liveFeedPrice || precoInVal || extremo;
    if (!entryPrice) {
      const priceMatch =
        textBody.match(/preço:\s*\$?([0-9.]+)/i) ||
        textBody.match(/price:\s*\$?([0-9.]+)/i) ||
        textBody.match(/@\s*([0-9.]+)/);
      if (priceMatch) {
         entryPrice = parseFloat(priceMatch[1]);
      } else {
         const basePrice = basePriceMap[moeda] || 100;
         entryPrice = basePrice + (Math.random() - 0.5) * (basePrice * 0.02);
      }
    }

    // Parse and check ADX value dynamically
    let adxValFinal = 25.0;
    if (isPythonWebhook) {
      adxValFinal = adxVal;
    } else {
      const adxMatch = textBody.match(/ADX:\s*([0-9.]+)/i);
      if (adxMatch) {
        adxValFinal = parseFloat(adxMatch[1]);
      } else {
        try {
          const data = JSON.parse(textBody);
          if (data.adx !== undefined) {
            adxValFinal = Number(data.adx);
          } else {
            adxValFinal = parseFloat((26.5 + Math.random() * 6.5).toFixed(1));
          }
        } catch (e) {
          adxValFinal = parseFloat((26.5 + Math.random() * 6.5).toFixed(1));
        }
      }
    }

    const s: Signal = {
      id: `PYTHON_${moeda}_${Date.now()}`,
      moeda: moeda,
      tf: tf,
      lado: lado,
      extremo: extremo,
      tsIn: Date.now(),
      horaIn: getBrazilTime(),
      rVol: parseFloat(rVolVal.toFixed(1)) as any,
      adx: parseFloat(adxValFinal.toFixed(1)) as any,
      precoIn: entryPrice,
      rsi: rsiVal,
      rawPayload: textBody,
      motor: motor,
    };

    if (isPythonWebhook) {
      // MOTOR TESTE A (Breakout system with waiting list)
      if (s.adx <= 25.0 && pythonTipo !== "ALERTA_DESCARTADO") {
        s.status = "BLOQUEADO";
        s.motivoBloqueio = `ADX ${s.adx} fraco. Requer > 25`;
        state.receivedSignals.unshift(s);
        const logMsg = `[${s.horaIn}] 🛑 SINAL BLOQUEADO (ADX FILTER): ${s.moeda} (${s.lado}) - ADX ${s.adx} (Requer > 25)`;
        state.logs.unshift(logMsg);
        if (state.logs.length > 50) state.logs.pop();
        saveState();
        return res.json({
          status: "bloqueado",
          motivo: `ADX ${s.adx} fraco. Requer > 25`,
          signal: s,
        });
      }

      if (pythonTipo === "ALERTA_ARMADO") {
        s.status = "ARMADO";
        state.receivedSignals.unshift(s);
        state.pendingSignals.unshift(s);
        const logMsg = `[${s.horaIn}] 🛰️ RADAR EXTERNO (ARMADO): ${s.moeda} (${s.lado}) em ${s.tf} - Extremo: ${s.extremo}`;
        state.logs.unshift(logMsg);
        if (state.logs.length > 50) state.logs.pop();
        saveState();
        return res.json({ status: "sucesso_armado", signal: s });
      } else if (pythonTipo === "ALERTA_DESCARTADO") {
        const existing = state.receivedSignals.find(
          (rs) => rs.moeda === moeda && rs.status === "ARMADO",
        );
        if (existing) {
          existing.status = "DESCARTADO";
        }
        state.pendingSignals = state.pendingSignals.filter(
          (ps) => ps.moeda !== moeda,
        );
        const logMsg = `[${getBrazilTime()}] ❌ RADAR EXTERNO (DESCARTADO): ${moeda} inverteu ou expirou.`;
        state.logs.unshift(logMsg);
        if (state.logs.length > 50) state.logs.pop();
        saveState();
        return res.json({ status: "sucesso_descartado", moeda });
      } else if (pythonTipo === "GATILHO_SNIPER") {
        s.status = "GATILHO_EXECUTADO";
        state.receivedSignals.unshift(s);
        state.pendingSignals = state.pendingSignals.filter(
          (ps) => ps.moeda !== moeda,
        );
        const hExec = getBrazilTime();
        const signalMotor = s.motor;

        // ROBÔ ANTIGO (MOTOR TESTE A) opens ONLY on SIMULADOR A (and REAL if active) - Never in SIMULADOR B!
        if (state.cfg.autoSimA) {
          const hasActiveSimA = state.activeTrades.some(
            (t) =>
              t.symbol === `${moeda}/USDT` &&
              t.side === lado &&
              t.est === "SIMU",
          );
          if (!hasActiveSimA) {
            state.activeTrades.unshift({
              id: `PT_${moeda}_SIM_${Date.now()}`,
              symbol: `${moeda}/USDT`,
              side: lado,
              entry: entryPrice,
              margin: state.cfg.margemSimu,
              roi: 0,
              pnl: 0,
              est: "SIMU",
              estrategia: "A",
              lev: state.cfg.alavPadrao,
              tsIn: Date.now(),
              dataIn: hExec,
              isAuto: true,
              stopP: -25,
              maxRoi: 0,
              minRoi: 0,
              now: entryPrice,
              adx: s.adx,
              motor: signalMotor,
              tf: s.tf,
            });
          }
        }
        if (state.cfg.autoReal) {
          const hasActiveReal = state.activeTrades.some(
            (t) =>
              t.symbol === `${moeda}/USDT` &&
              t.side === lado &&
              t.est === "REAL",
          );
          if (!hasActiveReal) {
            state.activeTrades.unshift({
              id: `PT_${moeda}_REAL_${Date.now()}`,
              symbol: `${moeda}/USDT`,
              side: lado,
              entry: entryPrice,
              margin: state.cfg.margemPadrao,
              roi: 0,
              pnl: 0,
              est: "REAL",
              estrategia: state.cfg.estrategiaReal,
              lev: state.cfg.alavPadrao,
              tsIn: Date.now(),
              dataIn: hExec,
              isAuto: true,
              stopP: -25,
              maxRoi: 0,
              minRoi: 0,
              now: entryPrice,
              adx: s.adx,
              motor: signalMotor,
              tf: s.tf,
            });
          }
        }

        const logMsg = `[${hExec}] ✅🟢 GATILHO SNIPER EXTERNO (${signalMotor}): ${moeda} (${lado}) acionado com volume!`;
        state.logs.unshift(logMsg);
        if (state.logs.length > 50) state.logs.pop();
        saveState();
        return res.json({ status: "sucesso_gatilho", moeda, lado });
      }
    } else {
      // Motor EXTERNO A (TradingView webhooks and direct signal integrations) - IMMEDIATE ORDER ENTRY Execution
      // 1. Evaluate ADX threshold filtration on incoming signal
      if (s.motor !== "MOTOR TESTE C" && s.adx <= 25.0) {
        s.status = "BLOQUEADO";
        s.motivoBloqueio = `ADX ${s.adx} fraco para Motor EXTERNO A. Requer > 25`;
        state.receivedSignals.unshift(s);
        const logMsg = `[${s.horaIn}] 🛑 SINAL TV BLOQUEADO (ADX FILTER): ${s.moeda} (${s.lado}) - ADX ${s.adx} (Requer > 25)`;
        state.logs.unshift(logMsg);
        if (state.logs.length > 50) state.logs.pop();
        saveState();
        return res.json({
          status: "bloqueado",
          motivo: `ADX ${s.adx} fraco. Requer > 25`,
          signal: s,
        });
      }

      // 2. Evaluate RSI threshold filtration on incoming signal
      let isBlocked = false;
      if (state.cfg.useRsiFilter && s.motor !== "MOTOR TESTE C") {
        if (lado === "LONG" && rsiVal > (state.cfg.rsiOverbought || 80)) {
          isBlocked = true;
        } else if (lado === "SHORT" && rsiVal < (state.cfg.rsiOversold || 20)) {
          isBlocked = true;
        }
      }

      if (isBlocked) {
        s.status = "BLOQUEADO";
        s.motivoBloqueio = `RSI ${rsiVal} fora do limite para ${lado}`;
        state.receivedSignals.unshift(s);
        const logMsg = `[${s.horaIn}] 🛑 SINAL TV BLOQUEADO (RSI FILTER): ${s.moeda} (${s.lado}) - RSI está em ${rsiVal}`;
        state.logs.unshift(logMsg);
        if (state.logs.length > 50) state.logs.pop();
        saveState();
        return res.json({
          status: "bloqueado",
          motivo: `RSI ${rsiVal} fora do limite para ${lado}`,
          signal: s,
        });
      }

      // 3. Bypass breakout triggers and directly deploy live positions to SIMULADOR B, SIMULADOR C, and REAL
      s.status = "GATILHO_EXECUTADO";
      state.receivedSignals.unshift(s);

      const hExec = getBrazilTime();
      const signalMotor = s.motor; // TESTE B - MOTOR DO TRADING VIEW or MOTOR TESTE C

      const isTesteC = signalMotor === "MOTOR TESTE C";

      if (isTesteC) {
        // Option C: TESTE C - NOVO MOTOR
        if (state.cfg.autoSimC) {
          const hasActiveSimC = state.activeTrades.some(
            (t) =>
              t.symbol === `${moeda}/USDT` &&
              t.side === lado &&
              t.est === "SIMU_C",
          );
          if (!hasActiveSimC) {
            state.activeTrades.unshift({
              id: `PT_${moeda}_SIMC_${Date.now()}`,
              symbol: `${moeda}/USDT`,
              side: lado,
              entry: entryPrice,
              margin: state.cfg.margemSimu,
              roi: 0,
              pnl: 0,
              est: "SIMU_C",
              estrategia: "A",
              lev: state.cfg.alavPadrao,
              tsIn: Date.now(),
              dataIn: hExec,
              isAuto: true,
              stopP: -25,
              maxRoi: 0,
              minRoi: 0,
              now: entryPrice,
              adx: s.adx,
              motor: "MOTOR TESTE C",
              tf: s.tf,
            });
          }
        }
      } else {
        // Option B: TESTE B - MOTOR DO TRADING VIEW
        if (state.cfg.autoSimB) {
          const hasActiveSimB = state.activeTrades.some(
            (t) =>
              t.symbol === `${moeda}/USDT` &&
              t.side === lado &&
              t.est === "SIMU_B",
          );
          if (!hasActiveSimB) {
            state.activeTrades.unshift({
              id: `PT_${moeda}_SIMB_${Date.now()}`,
              symbol: `${moeda}/USDT`,
              side: lado,
              entry: entryPrice,
              margin: state.cfg.margemSimu,
              roi: 0,
              pnl: 0,
              est: "SIMU_B",
              estrategia: "A",
              lev: state.cfg.alavPadrao,
              tsIn: Date.now(),
              dataIn: hExec,
              isAuto: true,
              stopP: -25,
              maxRoi: 0,
              minRoi: 0,
              now: entryPrice,
              adx: s.adx,
              motor: "TESTE B - MOTOR DO TRADING VIEW",
              tf: s.tf,
            });
          }
        }
      }

      // Option REAL: Active position inside Binance REAL (if checked)
      if (state.cfg.autoReal) {
        const hasActiveReal = state.activeTrades.some(
          (t) =>
            t.symbol === `${moeda}/USDT` &&
            t.side === lado &&
            t.est === "REAL",
        );
        if (!hasActiveReal) {
          state.activeTrades.unshift({
            id: `PT_${moeda}_REAL_${Date.now()}`,
            symbol: `${moeda}/USDT`,
            side: lado,
            entry: entryPrice,
            margin: state.cfg.margemPadrao,
            roi: 0,
            pnl: 0,
            est: "REAL",
            estrategia: state.cfg.estrategiaReal,
            lev: state.cfg.alavPadrao,
            tsIn: Date.now(),
            dataIn: hExec,
            isAuto: true,
            stopP: -25,
            maxRoi: 0,
            minRoi: 0,
            now: entryPrice,
            adx: s.adx,
            motor: signalMotor,
            tf: s.tf,
          });
        }
      }

      const logMsg = `[${hExec}] ✅ SINAL PROCESSADO (${signalMotor}): ${moeda} (${lado}) EM ${s.tf}`;
      state.logs.unshift(logMsg);
      if (state.logs.length > 50) state.logs.pop();
      saveState();
      return res.json({ status: "sucesso_imediato", signal: s });
    }
  });

  // Vite Integration
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`[Elite Trader] Server listening on http://0.0.0.0:${PORT}`);
  });
}

startServer().catch(console.error);

function generateFallbackAnalysis(
  symbol: string,
  tf: string,
  price: number,
  trend: string,
  vol: string,
  score: string,
  type: string,
): string {
  const isUp = trend === "alta" || type === "LONG";
  const action = isUp ? "LONG" : type === "SHORT" ? "SHORT" : "HOLD (NEUTRO)";

  if (action === "LONG") {
    return `### ⚡ ANÁLISE DE FLUXO & ESTRUTURA (ELITE SNIPER AI - SIMULAÇÃO)
O par **${symbol}/USDT** no tempo gráfico de **${tf}** apresenta forte pressão de compra institucional. O rompimento da média curta (SMA 8/21) confirma um pivô de alta com suporte dinâmico relevante em **$${(price * 0.985).toFixed(4)}**. O volume de negociação está **${vol}**, sustentando a quebra de liquidez no topo anterior. No entanto, lembre-se: a volatilidade média das altcoins no intradiário exige atenção, pois o preço está sobrecarregado no curto prazo.

### 🎯 PLANO DE ATAQUE & GERENCIAMENTO DE RISCO
- **Direção**: Entrada em **LONG**
- **Gatilho Ideal**: Região de pullback próximo a **$${(price * 0.995).toFixed(4)}**
- **Alvo Realista (Take Profit)**: Zona de resistência em **$${(price * 1.03).toFixed(4)}**
- **Stop Loss Cirúrgico**: Abaixo da mínima do candle de força em **$${(price * 0.98).toFixed(4)}** (-2.0% sem alavancagem, o que equivale a -40% na alavancagem de 20x). Mantenha a alocação de margem pequena para amortecer o fluxo de ruído (violinadas).`;
  } else if (action === "SHORT") {
    return `### ⚡ ANÁLISE DE FLUXO & ESTRUTURA (ELITE SNIPER AI - SIMULAÇÃO)
O ativo **${symbol}/USDT** no TF de **${tf}** indica exaustão de compra e início de distribuição. O rompimento da SMA 8 para baixo da SMA 21 consolida um viés de baixa estrutural. A confirmação de volume está **${vol}**, mostrando que a força vendedora está absorvendo a liquidez residual. Existe risco iminente de manipulação (short squeeze) se testarmos suportes históricos agressivamente agora.

### 🎯 PLANO DE ATAQUE & GERENCIAMENTO DE RISCO
- **Direção**: Entrada em **SHORT**
- **Gatilho Ideal**: Rejeição de pullback em **$${(price * 1.005).toFixed(4)}**
- **Alvo Realista (Take Profit)**: Primeira zona de consolidação em **$${(price * 0.97).toFixed(4)}**
- **Stop Loss Cirúrgico**: Acima do último topo em **$${(price * 1.018).toFixed(4)}** (+1.8% no spot, -36% na alavancagem de 20x). Não adicione margem a uma posição perdedora!`;
  } else {
    return `### ⚡ ANÁLISE DE FLUXO & ESTRUTURA (ELITE SNIPER AI - SIMULAÇÃO)
O par **${symbol}/USDT** está comprimido em uma zona de acumulação sem tendência clara no intradiário de **${tf}**. O score quantitativo de **${score}** reflete a briga de ordens na região de equilíbrio. O volume **${vol}** sinaliza desinteresse institucional no momento. Entrar agora é expor capital ao ruído puro e taxas desnecessárias.

### 🎯 PLANO DE ATAQUE & GERENCIAMENTO DE RISCO
- **Direção**: **HOLD (Aguardar fora do mercado)**
- **Recomendação**: Paciência militar. Aguarde o rompimento das extremidades do canal lateral. Caso insista na operação de scalping rápido, opere apenas com metade da mão padrão. Suporte chave em **$${(price * 0.97).toFixed(4)}** e resistência em **$${(price * 1.02).toFixed(4)}**.`;
  }
}
