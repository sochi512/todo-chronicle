import { ApplicationConfig, isDevMode } from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideFirebaseApp, initializeApp } from '@angular/fire/app';
import { getAuth, provideAuth } from '@angular/fire/auth';
import { environment } from '../environments/environment';
import { from, switchMap } from 'rxjs';
import { provideClientHydration } from '@angular/platform-browser';

/**
 * アプリケーション設定
 * 
 * このファイルは以下の機能を提供します：
 * - ルーティングの設定
 * - HTTPクライアントの設定（認証トークンの自動付与）
 * - Firebaseの初期化と認証設定
 * - クライアントサイドハイドレーションの設定
 * 
 * 各プロバイダーは以下の役割を持ちます：
 * - provideRouter: アプリケーションのルーティングを提供
 * - provideHttpClient: HTTPリクエストのインターセプターを設定
 * - provideFirebaseApp: Firebaseアプリケーションの初期化
 * - provideAuth: Firebase認証の初期化
 * - provideClientHydration: サーバーサイドレンダリングのサポート
 */
export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(
      withInterceptors([
        /**
         * HTTPリクエストのインターセプター
         * 認証済みユーザーのリクエストに自動的に認証トークンを付与します。
         * @param req 元のHTTPリクエスト
         * @param next 次のインターセプターまたはHTTPハンドラー
         * @returns 認証トークンが付与されたリクエストのObservable
         */
        (req, next) => {
          const auth = getAuth();
          const user = auth.currentUser;
          
          if (user) {
            return from(user.getIdToken()).pipe(
              switchMap(token => {
                const authReq = req.clone({
                  headers: req.headers.set('Authorization', `Bearer ${token}`)
                });
                return next(authReq);
              })
            );
          }
          
          return next(req);
        }
      ])
    ),
    /**
     * Firebaseアプリケーションの初期化
     * 環境設定に基づいてFirebaseアプリケーションを初期化します。
     * 初期化に失敗した場合はエラーをスローします。
     */
    provideFirebaseApp(() => {
      try {
        return initializeApp(environment.firebase);
      } catch (error) {
        console.error('Firebase initialization error:', error);
        throw error;
      }
    }),
    /**
     * Firebase認証の初期化
     * Firebase認証サービスを初期化します。
     * 初期化に失敗した場合はエラーをスローします。
     */
    provideAuth(() => {
      try {
        return getAuth();
      } catch (error) {
        console.error('Firebase Auth initialization error:', error);
        throw error;
      }
    }),
    provideClientHydration()
  ]
};
