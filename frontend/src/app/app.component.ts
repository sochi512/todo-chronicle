import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, Router } from '@angular/router';
import { DashboardService } from './services/dashboard.service';
import { AuthService } from './services/auth.service';
import { User as FirebaseUser } from '@angular/fire/auth';
import { Observable, filter, switchMap, map, tap, takeUntil, timeout, catchError, of, combineLatest, shareReplay } from 'rxjs';
import { Subject } from 'rxjs';
import { Task } from './models/types';

/**
 * アプリケーションのルートコンポーネント
 * 
 * このコンポーネントは以下の機能を提供します：
 * - 認証状態の管理と監視
 * - ダッシュボードデータの初期化と更新
 * - ユーザー情報の表示
 * - 経験値バーの管理
 * - 完了済タスク数の管理
 */
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit, OnDestroy {
  /** 現在のユーザー情報のObservable */
  user$: Observable<FirebaseUser | null>;
  
  /** 認証状態のObservable */
  isAuthenticated$: Observable<boolean>;
  
  /** ローディング状態のObservable */
  isLoading$: Observable<boolean>;
  
  /** ダッシュボードデータのObservable */
  dashboardData$: Observable<any>;
  
  /** 現在のシーズン情報 */
  currentSeason: any;
  
  /** 経験値の進捗率（0-100） */
  expPercentage = 0;
  
  /** コンポーネントの破棄時に使用するSubject */
  private destroy$ = new Subject<void>();

  /** 完了済タスク数 */
  completedTasksCount = 0;

  constructor(
    private authService: AuthService,
    private dashboardService: DashboardService,
    private router: Router
  ) {
    this.user$ = this.authService.user$.pipe(
      shareReplay(1)
    );

    this.dashboardData$ = this.dashboardService.dashboardData$.pipe(
      shareReplay(1)
    );

    // 認証状態の判定を簡素化
    this.isAuthenticated$ = this.user$.pipe(
      map(user => !!user),
      tap(isAuthenticated => {
        if (isAuthenticated && this.router.url === '/login') {
          this.router.navigate(['/']);
        } else if (!isAuthenticated && !this.router.url.includes('/login')) {
          this.router.navigate(['/login']);
        }
      }),
      shareReplay(1)
    ) as Observable<boolean>;

    // ローディング状態の管理を簡素化
    this.isLoading$ = combineLatest([
      this.authService.isInitialized$,
      this.dashboardService.initialized$,
      this.user$
    ]).pipe(
      map(([authInitialized, dashboardInitialized, user]) => {
        if (this.router.url.includes('/login')) {
          return false;
        }
        return !authInitialized || (!!user && !dashboardInitialized);
      }),
      shareReplay(1)
    );

    // ダッシュボードデータの変更を監視して完了済タスク数を更新
    this.dashboardData$.pipe(
      takeUntil(this.destroy$),
      map(data => data?.tasks || []),
      map((tasks: Task[]) => tasks.filter(task => task.status === 1 && !task.experienced_at).length)
    ).subscribe(count => {
      this.completedTasksCount = count;
    });
  }

  /**
   * コンポーネントの初期化時に実行されます。
   * ダッシュボードデータの購読を開始し、シーズン情報と経験値を更新します。
   */
  ngOnInit() {
    // ダッシュボードデータの購読（初期化後の更新用）
    this.dashboardService.dashboardData$.pipe(
      takeUntil(this.destroy$)
    ).subscribe(dashboard => {
      if (dashboard) {
        this.currentSeason = dashboard.seasons.find(season => season.id === dashboard.user.current_season_id);
        this.expPercentage = this.currentSeason ? this.calculateExpPercentage(this.currentSeason) : 0;
      } else {
        this.currentSeason = null;
        this.expPercentage = 0;
      }
    });
  }

  /**
   * コンポーネントの破棄時に実行されます。
   * サブスクリプションを解除し、メモリリークを防ぎます。
   */
  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }

  /**
   * ユーザーをサインアウトします。
   * ダッシュボードデータをリセットし、ログイン画面に遷移します。
   */
  signOut() {
    // ダッシュボードデータをリセット
    this.dashboardService.resetDashboard();
    this.currentSeason = null;
    this.expPercentage = 0;
    
    // 認証状態をリセット
    this.authService.signOut()
      .then(() => {
        // サインアウト成功後、即座にログイン画面へ遷移
        this.router.navigate(['/login'], { replaceUrl: true });
      })
      .catch(error => {
        console.error('AppComponent: サインアウトエラー:', error);
        // エラーが発生した場合も、ログイン画面へ遷移
        this.router.navigate(['/login'], { replaceUrl: true });
      });
  }

  /**
   * 経験値の進捗率を計算します。
   * @param season シーズン情報
   * @returns 経験値の進捗率（0-100）
   * @private
   */
  private calculateExpPercentage(season: any): number {
    if (!season) return 0;
    const currentExp = season.total_exp || 0;
    const requiredExp = season.required_exp || 1;
    return Math.min((currentExp / requiredExp) * 100, 100);
  }
}

