import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TaskListComponent } from '../../components/task-list/task-list.component';
import { StoryComponent } from '../../components/story/story.component';
import { DashboardService } from '../../services/dashboard.service';
import { Dashboard } from '../../models/types';
import { Subscription, takeUntil, filter, switchMap, combineLatest, tap, catchError, of } from 'rxjs';
import { Subject } from 'rxjs';
import { RouterModule } from '@angular/router';
import { Task } from '../../models/types';
import { AuthService } from '../../services/auth.service';
import { User } from '../../models/types';

/**
 * ホーム画面のコンポーネント
 * 
 * このコンポーネントは以下の機能を提供します：
 * - タスクとストーリーの2つのタブ表示（モバイル表示時）
 * - タスクとストーリーの2カラムレイアウト（デスクトップ表示時）
 * - タスクの管理（追加、編集、削除、完了状態の切り替え）
 * - ストーリーの表示とシーズン切り替え
 * 
 * 認証状態の変更を監視し、ユーザーがログインした際にダッシュボードデータを自動的に読み込みます。
 * ログイン直後はストーリータブを表示し、ユーザーの現在のシーズンを表示します。
 */
@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, TaskListComponent, StoryComponent, RouterModule],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss']
})
export class HomeComponent implements OnInit, OnDestroy {
  /** 現在選択中のタブ（'tasks'または'stories'） */
  currentTab: 'tasks' | 'stories' = 'tasks';
  
  /** ダッシュボードデータ。nullの場合はデータ未読み込み状態 */
  dashboardData: Dashboard | null = null;
  
  /** 選択中のシーズンID */
  selectedSeasonId?: string;
  
  /** ストーリーのローディング状態 */
  isStoryLoading = false;
  
  /** コンポーネントの破棄時に使用するSubject */
  private destroy$ = new Subject<void>();

  constructor(
    private dashboardService: DashboardService,
    private authService: AuthService
  ) {}

  /**
   * コンポーネントの初期化時に実行されます。
   * 認証状態の変更を監視し、ユーザーがログインした際にダッシュボードデータを読み込みます。
   */
  ngOnInit() {
    console.log('HomeComponent: ngOnInit 開始');
    
    // 認証状態の変更を監視
    combineLatest([
      this.authService.user$,
      this.authService.isInitialized$
    ]).pipe(
      takeUntil(this.destroy$),
      tap(([user, isInitialized]) => {
        console.log('HomeComponent: 認証状態確認:', { user, isInitialized });
      }),
      // 認証状態が初期化され、かつ認証済みユーザーが存在する場合のみ処理を続行
      filter(([user, isInitialized]) => {
        const shouldProceed = isInitialized && !!user;
        console.log('HomeComponent: 処理継続判定:', shouldProceed);
        return shouldProceed;
      }),
      switchMap(([user]) => {
        console.log('HomeComponent: ダッシュボードデータ取得開始');
        // データをクリアしてから新しいデータを読み込む
        this.clearData();
        
        const userData: User = {
          player_name: '',
          created_at: new Date(),
          current_season_id: '',
          season_ids: []
        };
        
        return this.dashboardService.initializeDashboard(userData).pipe(
          tap(data => {
            console.log('HomeComponent: ダッシュボード初期化成功:', data);
          }),
          catchError(error => {
            console.error('HomeComponent: ダッシュボード初期化エラー:', error);
            return of(null);
          })
        );
      })
    ).subscribe({
      next: (data) => {
        if (data) {
          this.dashboardData = data;
          this.dashboardService.updateDashboardData(data);
          // モバイル表示時はタスクタブを表示
          this.currentTab = 'tasks';
          // user.current_season_idのシーズンを表示
          this.selectedSeasonId = data.user.current_season_id;
        } else {
          this.clearData();
        }
      },
      error: (error) => {
        console.error('HomeComponent: ダッシュボードデータの読み込みに失敗しました:', error);
        this.clearData();
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
   * タブを切り替えます。
   * ストーリータブへの切り替え時はローディング中の場合、切り替えを無視します。
   * @param tab 切り替え先のタブ（'tasks'または'stories'）
   */
  switchTab(tab: 'tasks' | 'stories') {
    if (tab === 'stories' && this.isStoryLoading) {
      return;
    }
    this.currentTab = tab;
  }

  /**
   * タスクが更新された時の処理を行います。
   * ダッシュボードデータが存在しない場合は処理を行いません。
   * タスクの追加、更新、削除はローカルで完結するため、ダッシュボードの再取得は不要です。
   */
  onTaskUpdated() {
    if (!this.dashboardData) return;
    this.dashboardService.updateDashboardData(this.dashboardData);
  }

  /**
   * シーズンが選択された時の処理を行います。
   * 選択されたシーズンIDを保存し、モバイル表示の場合はストーリータブに切り替えます。
   * @param seasonId 選択されたシーズンID
   */
  onSeasonSelected(seasonId: string) {
    this.selectedSeasonId = seasonId;
    this.currentTab = 'stories';
  }

  /**
   * ダッシュボードデータを読み込みます。
   * データの読み込みに成功した場合はダッシュボードデータを更新し、
   * 失敗した場合はデータをクリアします。
   * @private
   */
  private loadDashboardData() {
    this.dashboardService.getDashboard().subscribe({
      next: (data) => {
        if (data) {
          this.dashboardData = data;
          this.dashboardService.updateDashboardData(data);
        } else {
          this.clearData();
        }
      },
      error: (error) => {
        console.error('ダッシュボードデータの読み込みに失敗しました:', error);
        this.clearData();
      }
    });
  }

  /**
   * データをクリアします。
   * ダッシュボードデータをnullに設定し、タブをタスクタブに戻します。
   * @private
   */
  private clearData() {
    this.dashboardData = null;
    this.currentTab = 'tasks';
  }

  /**
   * ストーリーのローディング状態が変更された時の処理を行います。
   * @param isLoading ローディング状態
   */
  onStoryLoading(isLoading: boolean) {
    this.isStoryLoading = isLoading;
  }
} 