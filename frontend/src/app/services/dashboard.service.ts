import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, BehaviorSubject, catchError, switchMap, tap, throwError, shareReplay, filter } from 'rxjs';
import { Dashboard, User } from '../models/types';
import { environment } from '../../environments/environment';
import { User as FirebaseUser } from '@angular/fire/auth';

/**
 * ダッシュボードサービス
 * 
 * このサービスは以下の機能を提供します：
 * - ダッシュボードデータの取得と管理
 * - ユーザー情報の初期化と更新
 * - タスクとシーズン情報の同期
 * - ダッシュボードの状態管理
 */
@Injectable({
  providedIn: 'root'
})
export class DashboardService {
  /** ダッシュボードデータを保持するSubject */
  private dashboardData = new BehaviorSubject<Dashboard | null>(null);
  
  /** 初期化状態を管理するSubject */
  private initialized = new BehaviorSubject<boolean>(false);

  /** ダッシュボードデータのObservable */
  dashboardData$ = this.dashboardData.asObservable().pipe(
    shareReplay(1)
  );
  
  /** 初期化状態のObservable */
  initialized$ = this.initialized.asObservable().pipe(
    shareReplay(1)
  );

  constructor(private http: HttpClient) {}

  /**
   * ダッシュボードデータをリセットします。
   * データと初期化状態をnullに設定します。
   */
  resetDashboard() {
    this.dashboardData.next(null);
    this.initialized.next(false);
  }

  /**
   * ダッシュボードデータを初期化します。
   * 既存のデータがある場合はそれを返し、ない場合は新規作成します。
   * @param user 初期化に使用するユーザー情報
   * @returns 初期化されたダッシュボードデータのObservable
   */
  initializeDashboard(user: User): Observable<Dashboard> {
    // 既に初期化済みの場合は何もしない
    if (this.initialized.getValue()) {
      return this.dashboardData$.pipe(
        filter((data): data is Dashboard => data !== null)
      );
    }
    
    return this.getDashboard().pipe(
      tap(data => {
        this.dashboardData.next(data);
        this.initialized.next(true);
      }),
      catchError(error => {
        if (error.status === 404) {
          return this.createUser(user).pipe(
            tap(data => {
              this.dashboardData.next(data);
              this.initialized.next(true);
            })
          );
        }
        this.initialized.next(true);
        return throwError(() => error);
      })
    );
  }

  /**
   * ダッシュボードデータを取得します。
   * APIから最新のデータを取得し、ローカルの状態を更新します。
   * @returns ダッシュボードデータのObservable
   */
  getDashboard(): Observable<Dashboard> {
    return this.http.get<Dashboard>(`${environment.apiUrl}/users/me/dashboard`).pipe(
      tap(data => {
        this.dashboardData.next(data);
        this.initialized.next(true);
      }),
      catchError(error => {
        this.initialized.next(true);
        return throwError(() => error);
      }),
      shareReplay(1)
    );
  }

  /**
   * ダッシュボードデータを更新します。
   * ローカルの状態を新しいデータで更新します。
   * @param data 更新するダッシュボードデータ
   */
  updateDashboardData(data: Dashboard) {
    if (data) {
      this.dashboardData.next(data);
      this.initialized.next(true);
    }
  }

  /**
   * 初期化状態をリセットします。
   * データと初期化状態をクリアします。
   */
  resetInitialization() {
    this.initialized.next(false);
    this.dashboardData.next(null);
  }

  /**
   * ユーザーを作成します。
   * @param user 作成するユーザー情報
   * @returns 作成されたダッシュボードデータのObservable
   * @private
   */
  private createUser(user: User): Observable<Dashboard> {
    return this.http.post<Dashboard>(`${environment.apiUrl}/users`, user).pipe(
      tap(data => {
        this.dashboardData.next(data);
        this.initialized.next(true);
      }),
      catchError(error => {
        this.initialized.next(true);
        throw error;
      })
    );
  }

  /**
   * テスト用のダッシュボードデータを取得します。
   * 開発時のテスト用に使用します。
   * @returns テスト用のダッシュボードデータ
   */
  getTestDashboardData(): Dashboard {
    // テストデータ
    const testData: Dashboard = {
      user: {
        player_name: 'テスト冒険者',
        created_at: new Date('2023-01-01T00:00:00Z'),
        current_season_id: 'season2',
        season_ids: ['season1', 'season2']
      },
      tasks: [
        {
          id: 'task1',
          title: '週報作成',
          due_date: new Date('2023-01-10T00:00:00Z'),
          status: 0,
          created_at: new Date('2023-01-01T00:00:00Z'),
          completed_at: undefined
        },
        {
          id: 'task2',
          title: '筋トレ30分',
          due_date: new Date('2023-01-15T00:00:00Z'),
          status: 1,
          created_at: new Date('2023-01-02T00:00:00Z'),
          completed_at: new Date('2023-01-15T00:00:00Z')
        }
      ],
      seasons: [
        {
          id: 'season1',
          season_no: 1,
          total_exp: 0,
          current_chapter: 2,
          current_phase: 1,
          previous_summary: '冒険の始まり',
          created_at: new Date('2023-01-01T00:00:00Z'),
          updated_at: new Date('2023-01-15T00:00:00Z'),
          required_exp: 1000,
          stories: [
            {
              id: 'story1',
              season_id: 'season1',
              chapter_no: 1,
              title: '週報作成の記録',
              content: '一週間の戦歴を巻物に記した',
              insight: '記録を残すことで成長を実感できる',
              phase: 0,
              created_at: new Date('2023-01-01T00:00:00Z'),
              summary: '週報作成の記録'
            },
            {
              id: 'story2',
              season_id: 'season1',
              chapter_no: 2,
              title: '筋トレの記録',
              content: '鍛錬の斧を振るい続けた',
              insight: '継続は力なり',
              phase: 1,
              created_at: new Date('2023-01-15T00:00:00Z'),
              summary: '筋トレの記録'
            }
          ]
        },
        {
          id: 'season2',
          season_no: 2,
          total_exp: 600,
          current_chapter: 3,
          current_phase: 2,
          previous_summary: '新たな挑戦',
          created_at: new Date('2023-02-01T00:00:00Z'),
          updated_at: new Date('2023-02-15T00:00:00Z'),
          required_exp: 2000,
          stories: [
            {
              id: 'story3',
              season_id: 'season2',
              chapter_no: 1,
              title: '新シーズンの始まり',
              content: '新たな冒険の始まり',
              insight: '挑戦は成長の糧',
              phase: 0,
              created_at: new Date('2023-02-01T00:00:00Z'),
              summary: '新シーズンの始まり'
            }
          ]
        }
      ]
    };
    return testData;
  }

  /**
   * 現在のダッシュボードデータを取得します。
   * @returns 現在のダッシュボードデータ、未初期化の場合はnull
   */
  getCurrentDashboardData(): Dashboard | null {
    return this.dashboardData.getValue();
  }
} 