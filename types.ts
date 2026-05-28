export interface Trade {
  id: string;
  symbol: string;
  side: 'LONG' | 'SHORT';
  entry: number;
  margin: number;
  roi: number;
  pnl: number;
  est: 'REAL' | 'SIMU' | 'SIMU_B' | 'SIMU_C';
  estrategia: string;
  lev: number;
  tsIn: number;
  dataIn: string;
  dataFim?: string;
  isAuto: boolean;
  stopP: number;
  maxRoi: number;
  minRoi: number;
  now?: number;
  motivo?: string;
  fezParcial?: boolean;
  tsFim?: number;
  tempoAtePicoMin?: number;
  tempoAtePocoMin?: number;
  rVol?: number;
  adx?: number;
  motor?: string;
  tf?: string;
  isSurfing?: boolean;
}

export interface Signal {
  id: string;
  moeda: string;
  tf: string;
  lado: 'LONG' | 'SHORT';
  extremo: number;
  tsIn: number;
  horaIn: string;
  rVol: number;
  adx: number;
  precoIn: number;
  rsi?: number;
  rawPayload?: string;
  status?: 'BLOQUEADO' | 'ARMADO' | 'DESCARTADO' | 'GATILHO_EXECUTADO' | 'PENDENTE';
  motivoBloqueio?: string;
  motor?: string;
}

export interface SystemStats {
  real: { w: number; l: number };
  simu: { w: number; l: number };
  simu_b: { w: number; l: number };
}

export interface BotState {
  balance: number;
  simuBalance: number;
  logs: string[];
  activeTrades: Trade[];
  history: Trade[];
  pendingSignals: Signal[];
  receivedSignals: Signal[];
  cfg: {
    radarAtivo: boolean;
    autoReal: boolean;
    autoSimA: boolean;
    autoSimB: boolean;
    autoSimC: boolean;
    maxAutoReal: number;
    margemPadrao: number;
    margemSimu: number;
    alavPadrao: number;
    estrategiaReal: string;
    volatilityThreshold?: number;
    dailyProfitGoal?: number;
    drawdownThreshold?: number;
    dailyLossLimit?: number;
    maxConsecutiveLosses?: number;
    binanceKey?: string;
    binanceSecret?: string;
    tgTokenArmado?: string;
    tgTokenExecutado?: string;
    tgChatId?: string;
    lovableWebhookUrl?: string;
    lovableWebhookSecret?: string;
    flaskWebhookSecret?: string;
    useRsiFilter?: boolean;
    rsiOverbought?: number;
    rsiOversold?: number;
    enableRsiAudioAlert?: boolean;
    enableRsiVisualAlert?: boolean;
    rsiMonitoredCoins?: string;
  };
  scanningStatus: string;
  btcTrend: string;
}
