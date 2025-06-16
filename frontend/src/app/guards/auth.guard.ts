import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { map, take, filter, tap } from 'rxjs/operators';
import { of } from 'rxjs';

/**
 * 認証ガード
 * ルートの保護に使用され、ユーザーの認証状態を確認します。
 * 
 * 機能：
 * - ユーザーが認証済みの場合、ルートへのアクセスを許可
 * - 未認証の場合、ログインページにリダイレクト
 * 
 * @returns Observable<boolean> 認証状態に基づいてtrue/falseを返すObservable
 */
export const AuthGuard = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  console.log('AuthGuard: 開始');

  return authService.user$.pipe(
    take(1),
    tap(user => {
      console.log('AuthGuard: 認証状態:', user ? '認証済み' : '未認証');
    }),
    map(user => {
      if (user) {
        console.log('AuthGuard: 認証済みのため、アクセスを許可');
        return true;
      } else {
        console.log('AuthGuard: 未認証のため、ログインページにリダイレクト');
        router.navigate(['/login']);
        return false;
      }
    })
  );
}; 