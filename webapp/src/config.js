// Supabase publishable 設定（client 用，安全公開）。
// 可用 Vercel 環境變數 VITE_SUPABASE_URL / VITE_SUPABASE_KEY 覆蓋。
export const SUPABASE_URL =
  import.meta.env.VITE_SUPABASE_URL || 'https://cmtubaxlniglklmdwlzs.supabase.co'
export const SUPABASE_KEY =
  import.meta.env.VITE_SUPABASE_KEY || 'sb_publishable_14eHJNNxAJC1arpj9xM58Q_2Z-EtEtG'
