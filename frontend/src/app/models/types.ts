/**
 * タスクの状態を表す列挙型
 */
export enum TaskStatus {
  PENDING = 0,    // 未完了
  COMPLETED = 1   // 完了
}

/**
 * ストーリーの進行段階を表す列挙型
 * 起承転結の物語構造に基づいています
 */
export enum StoryPhase {
  KI = 0,    // 起：物語の始まり
  SHO = 1,   // 承：展開
  TEN = 2,   // 転：転換点
  KETSU = 3, // 結：結末
  KAN = 4    // 完：完結
}

/**
 * タスクの情報を表すインターフェース
 */
export interface Task {
  id?: string;              // タスクの一意識別子
  title: string;            // タスクのタイトル
  due_date?: Date;          // 期限日
  status: TaskStatus;       // タスクの状態
  created_at: Date;         // 作成日時
  completed_at?: Date;      // 完了日時
  experienced_at?: Date;    // 経験値獲得日時
}

/**
 * ストーリーの情報を表すインターフェース
 */
export interface Story {
  id?: string;                          // ストーリーの一意識別子
  season_id: string;                    // 所属するシーズンのID
  chapter_no: number;                   // チャプター番号
  title: string;                        // ストーリーのタイトル
  content: string;                      // ストーリーの本文
  insight: string;                      // 洞察
  phase: StoryPhase;                    // ストーリーの進行段階
  created_at: Date;                     // 作成日時
  summary?: string;                     // 要約
  completed_tasks?: Array<{ [key: string]: string }>;  // 完了したタスクの情報
  imageUrl?: string;                    // ストーリーに関連する画像のURL
}

/**
 * シーズンの情報を表すインターフェース
 */
export interface Season {
  id?: string;              // シーズンの一意識別子
  season_no: number;        // シーズン番号
  total_exp: number;        // 累計経験値
  current_chapter: number;  // 現在のチャプター番号
  current_phase: StoryPhase;// 現在の進行段階
  previous_summary: string; // 前回の要約
  created_at: Date;         // 作成日時
  updated_at?: Date;        // 更新日時
  required_exp: number;     // 次のレベルに必要な経験値
  stories: Story[];         // シーズンに属するストーリーの配列
}

/**
 * ユーザーの情報を表すインターフェース
 */
export interface User {
  player_name?: string;     // プレイヤー名
  created_at: Date;         // アカウント作成日時
  current_season_id?: string;// 現在のシーズンID
  season_ids: string[];     // 参加したシーズンのID配列
}

/**
 * ダッシュボードの情報を表すインターフェース
 */
export interface Dashboard {
  user: User;               // ユーザー情報
  tasks: Task[];            // タスク一覧
  seasons: Season[];        // シーズン一覧
} 