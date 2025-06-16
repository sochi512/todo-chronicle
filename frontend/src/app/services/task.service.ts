import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject, catchError, tap, throwError } from 'rxjs';
import { Task, TaskStatus, Story, Season } from '../models/types';
import { environment } from '../../environments/environment';

/**
 * タスク管理サービス
 * 
 * このサービスは以下の機能を提供します：
 * - タスクの作成、更新、削除（CRUD操作）
 * - タスクステータスの管理
 * - タスク一覧の状態管理
 * - ユーザー経験値の更新
 * 
 * タスクの状態変更はリアルタイムで反映され、関連するコンポーネントに通知されます。
 */
@Injectable({
  providedIn: 'root'
})
export class TaskService {
  /** タスク一覧の状態を管理するSubject */
  private tasksSubject = new BehaviorSubject<Task[]>([]);
  /** タスク一覧のObservable */
  tasks$ = this.tasksSubject.asObservable();

  constructor(private http: HttpClient) {}

  /**
   * タスクを作成します。
   * 作成されたタスクは自動的にタスク一覧に追加されます。
   * @param task 作成するタスクの情報（id, created_at, completed_atを除く）
   * @returns 作成されたタスクのObservable
   */
  createTask(task: Omit<Task, 'id' | 'created_at' | 'completed_at'>): Observable<Task> {
    return this.http.post<Task>(`${environment.apiUrl}/users/me/tasks`, task).pipe(
      tap(newTask => {
        console.log('TaskService: タスク作成成功:', newTask);
        const currentTasks = this.tasksSubject.getValue();
        this.tasksSubject.next([...currentTasks, newTask]);
      }),
      catchError(error => {
        console.error('TaskService: タスク作成エラー:', error);
        return throwError(() => error);
      })
    );
  }

  /**
   * タスクを更新します。
   * 更新されたタスクは自動的にタスク一覧に反映されます。
   * @param taskId 更新対象のタスクID
   * @param updates 更新するタスクの情報
   * @returns 更新されたタスクのObservable
   */
  updateTask(taskId: string, updates: Partial<Task>): Observable<Task> {
    return this.http.put<Task>(`${environment.apiUrl}/users/me/tasks/${taskId}`, updates).pipe(
      tap(updatedTask => {
        console.log('TaskService: タスク更新成功:', updatedTask);
        const currentTasks = this.tasksSubject.getValue();
        const updatedTasks = currentTasks.map(task => 
          task.id === taskId ? updatedTask : task
        );
        this.tasksSubject.next(updatedTasks);
      }),
      catchError(error => {
        console.error('TaskService: タスク更新エラー:', error);
        return throwError(() => error);
      })
    );
  }

  /**
   * タスクを削除します。
   * 削除されたタスクは自動的にタスク一覧から除外されます。
   * @param taskId 削除対象のタスクID
   * @returns 削除操作のObservable
   */
  deleteTask(taskId: string): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/users/me/tasks/${taskId}`).pipe(
      tap(() => {
        console.log('TaskService: タスク削除成功:', taskId);
        const currentTasks = this.tasksSubject.getValue();
        const updatedTasks = currentTasks.filter(task => task.id !== taskId);
        this.tasksSubject.next(updatedTasks);
      }),
      catchError(error => {
        console.error('TaskService: タスク削除エラー:', error);
        return throwError(() => error);
      })
    );
  }

  /**
   * タスクのステータスを更新します。
   * ステータスの変更は自動的にタスク一覧に反映されます。
   * @param taskId 更新対象のタスクID
   * @param status 新しいステータス
   * @returns 更新されたタスクのObservable
   */
  updateTaskStatus(taskId: string, status: TaskStatus): Observable<Task> {
    const url = `${environment.apiUrl}/users/me/tasks/${taskId}/status`;
    return this.http.put<Task>(url, { status: Number(status) }).pipe(
      tap(updatedTask => {
        console.log('TaskService: タスクステータス更新成功:', updatedTask);
        const currentTasks = this.tasksSubject.getValue();
        const updatedTasks = currentTasks.map(task => 
          task.id === taskId ? updatedTask : task
        );
        this.tasksSubject.next(updatedTasks);
      }),
      catchError(error => {
        console.error('TaskService: タスクステータス更新エラー:', error);
        return throwError(() => error);
      })
    );
  }

  /**
   * 現在のタスク一覧を取得します。
   * このメソッドはSubjectの現在の値を返します。
   * @returns 現在のタスク一覧
   */
  getCurrentTasks(): Task[] {
    return this.tasksSubject.getValue();
  }

  /**
   * ユーザーの経験値を更新します。
   * タスクの完了やステータス変更に伴い呼び出されます。
   * @returns 更新結果のObservable
   */
  updateUserExperience(): Observable<any> {
    return this.http.put(`${environment.apiUrl}/users/me/experience`, {}).pipe(
      tap(response => {
        console.log('TaskService: 経験値更新成功:', response);
      }),
      catchError(error => {
        console.error('TaskService: 経験値更新エラー:', error);
        return throwError(() => error);
      })
    );
  }
} 