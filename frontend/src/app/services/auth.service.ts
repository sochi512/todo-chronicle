import { Injectable } from '@angular/core';
import { Auth, GoogleAuthProvider, signInWithPopup, signOut, User } from '@angular/fire/auth';
import { BehaviorSubject, Observable, from } from 'rxjs';
import { map, tap, shareReplay } from 'rxjs/operators';

/**
 * 認証サービス
 * 
 * このサービスは以下の機能を提供します：
 * - Googleアカウントによる認証
 * - 認証状態の管理と監視
 * - ユーザー情報の取得
 * - 認証トークンの管理
 */
@Injectable({
  providedIn: 'root'
})
export class AuthService {
  /** 現在のユーザー情報を保持するSubject */
  private userSubject = new BehaviorSubject<User | null>(null);
  
  /** 認証状態の初期化完了を管理するSubject */
  private initializedSubject = new BehaviorSubject<boolean>(false);

  constructor(private auth: Auth) {
    // 認証状態の初期化
    this.auth.onAuthStateChanged(async user => {
      console.log('AuthService: 認証状態が変更されました:', user);
      this.userSubject.next(user);
      this.initializedSubject.next(true);
    });
  }

  /**
   * 現在のユーザー情報をObservableとして取得します。
   * 認証状態の変更を監視できます。
   * @returns ユーザー情報のObservable
   */
  get user$(): Observable<User | null> {
    return this.userSubject.asObservable().pipe(
      tap(user => {
        if (!this.initializedSubject.value) {
          console.log('AuthService: 認証状態の初期化中...');
        }
      }),
      shareReplay(1)
    );
  }

  /**
   * 認証状態の初期化完了をObservableとして取得します。
   * @returns 初期化状態のObservable
   */
  get isInitialized$(): Observable<boolean> {
    return this.initializedSubject.asObservable().pipe(
      shareReplay(1)
    );
  }

  /**
   * Googleアカウントでサインインします。
   * @returns サインインしたユーザー情報
   * @throws サインインに失敗した場合にエラーをスロー
   */
  async signInWithGoogle(): Promise<User> {
    const provider = new GoogleAuthProvider();
    try {
      const result = await signInWithPopup(this.auth, provider);
      return result.user;
    } catch (error) {
      console.error('AuthService: Googleログインエラー:', error);
      throw error;
    }
  }

  /**
   * サインアウトします。
   * @throws サインアウトに失敗した場合にエラーをスロー
   */
  async signOut(): Promise<void> {
    try {
      await signOut(this.auth);
    } catch (error) {
      console.error('AuthService: サインアウトエラー:', error);
      throw error;
    }
  }

  /**
   * 現在のユーザー情報を取得します。
   * @returns 現在のユーザー情報、未認証の場合はnull
   */
  getCurrentUser(): User | null {
    return this.auth.currentUser;
  }

  /**
   * 現在のユーザーIDを取得します。
   * @returns ユーザーID、未認証の場合はnull
   */
  getUserId(): string | null {
    return this.auth.currentUser?.uid || null;
  }

  /**
   * 現在のユーザーの認証トークンを取得します。
   * @returns 認証トークン、未認証の場合はnull
   * @throws トークン取得に失敗した場合にエラーをスロー
   */
  async getAuthToken(): Promise<string | null> {
    const user = this.auth.currentUser;
    if (user) {
      try {
        return await user.getIdToken(true);
      } catch (error) {
        console.error('AuthService: トークン取得エラー:', error);
        return null;
      }
    }
    return null;
  }
} 