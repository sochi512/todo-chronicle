import { Routes } from '@angular/router';
import { HomeComponent } from './pages/home/home.component';
import { LoginComponent } from './pages/login/login.component';
import { AuthGuard } from './guards/auth.guard';

/**
 * アプリケーションのルーティング設定
 * 
 * このファイルは以下のルートを定義します：
 * - ルートパス（'/'）: ホーム画面（認証必須）
 * - ログインパス（'/login'）: ログイン画面
 * - その他のパス: ホーム画面にリダイレクト
 * 
 * 各ルートの設定：
 * - パス: アクセスするURLパス
 * - コンポーネント: 表示するコンポーネント
 * - ガード: アクセス制御（認証状態の確認など）
 */
export const routes: Routes = [
  {
    path: '',
    component: HomeComponent,
    canActivate: [AuthGuard]  // 認証済みユーザーのみアクセス可能
  },
  {
    path: 'login',
    component: LoginComponent  // ログイン画面は認証不要
  },
  {
    path: '**',
    redirectTo: ''  // 未定義のパスはホーム画面にリダイレクト
  }
];
