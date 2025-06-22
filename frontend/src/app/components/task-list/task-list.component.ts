import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, NgForm } from '@angular/forms';
import { Task, TaskStatus, Season } from '../../models/types';
import { trigger, transition, style, animate, state } from '@angular/animations';
import { TaskService } from '../../services/task.service';
import { DashboardService } from '../../services/dashboard.service';
import { DateFormatPipe } from '../../pipes/date-format.pipe';

/**
 * タスクリストコンポーネント
 * タスクの一覧表示、追加、編集、削除、完了状態の切り替えなどの機能を提供します。
 * また、タスク完了時の経験値獲得機能も実装しています。
 */
@Component({
  selector: 'app-task-list',
  standalone: true,
  imports: [CommonModule, FormsModule, DateFormatPipe],
  templateUrl: './task-list.component.html',
  styleUrls: ['./task-list.component.scss'],
  animations: [
    trigger('taskAnimation', [
      state('void', style({
        opacity: 1,
        transform: 'translateX(0)'
      })),
      state('active', style({
        transform: 'translateX(0)',
        opacity: 1
      })),
      // タスクの削除
      transition('* => void', [
        style({ transform: 'translateX(0)', opacity: 1 }),
        animate('300ms ease-out', style({ transform: 'translateX(100%)', opacity: 0 }))
      ])
    ])
  ]
})
export class TaskListComponent implements OnChanges, OnInit {
  /** 表示するタスク一覧 */
  @Input() tasks: Task[] = [];
  /** コンポーネントの有効/無効状態 */
  @Input() isEnabled = false;
  /** モバイル表示かどうか */
  @Input() isMobile = false;
  /** ストーリー生成中かどうか */
  @Input() isStoryLoading = false;
  /** タスク更新時のイベント */
  @Output() taskUpdated = new EventEmitter<void>();
  /** シーズン選択時のイベント */
  @Output() seasonSelected = new EventEmitter<string>();
  /** ストーリー読み込み状態の変更イベント */
  @Output() storyLoading = new EventEmitter<boolean>();
  /** ストーリー更新時のイベント */
  @Output() storyUpdated = new EventEmitter<void>();
  
  /** モーダルの表示状態 */
  showModal = false;
  /** 編集中のタスク */
  editingTask: Task | null = null;
  /** 全タスク表示モードかどうか */
  showAllTasks = false;
  /** 初期読み込み中かどうか */
  isInitialLoad = true;
  /** 経験値更新中かどうか */
  isUpdatingExperience = false;
  /** タスクフォームのデータ */
  taskForm: {
    title: string;
    dueDate: string | undefined;
    category: number | undefined;
  } = {
    title: '',
    dueDate: undefined,
    category: undefined
  };

  /** 削除確認モーダルの表示状態 */
  showDeleteConfirm = false;
  /** 削除対象のタスク */
  taskToDelete: Task | null = null;
  /** タスク保存処理中かどうか */
  isSavingTask = false;

  /**
   * タスクリストコンポーネントのコンストラクタ
   * @param taskService タスク管理サービス
   * @param dashboardService ダッシュボード管理サービス
   */
  constructor(private taskService: TaskService, private dashboardService: DashboardService) {}

  /**
   * コンポーネントの初期化時に実行されます。
   * 初期表示時のアニメーションを制御します。
   */
  ngOnInit() {
    console.log('ngOnInit isEnabled:', this.isEnabled);
    // 初期表示時のアニメーションを無効化
    this.isInitialLoad = true;
    setTimeout(() => {
      this.isInitialLoad = false;
    }, 100);
  }

  /**
   * 入力プロパティの変更を監視し、必要な処理を実行します。
   * @param changes 変更されたプロパティの情報
   */
  ngOnChanges(changes: SimpleChanges) {
    if (changes['isEnabled']) {
      console.log('ngOnChanges isEnabled:', changes['isEnabled'].currentValue);
      // 必要ならここで初期化や状態更新処理を追加
    }
    if (changes['tasks']) {
      if (!this.tasks.length) {
        this.closeModal();
      }
      this.isInitialLoad = true;
      setTimeout(() => {
        this.isInitialLoad = false;
      }, 100);
    }
  }

  /**
   * カテゴリーの表示用テキストを取得します。
   * @param category カテゴリーの数値
   * @returns カテゴリーの表示テキスト
   */
  getCategoryDisplay(category: number | undefined): string {
    switch (category) {
      case 1: return '💼 仕事';
      case 2: return '🏃 健康';
      case 3: return '📖 学習';
      case 4: return '🧺 生活';
      case 5: return '🧩 趣味';
      case 6: return '🌐 その他';
      default: return '🌐 その他';
    }
  }

  /**
   * 表示するタスク一覧を取得します。
   * showAllTasksがtrueの場合は全タスク、falseの場合は未完了タスクのみを返します。
   * タスクは以下の順でソートされます：
   * 1. ステータスの昇順（未完了→完了）
   * 2. 作成日時の降順（新しい順）
   * @returns {Task[]} 表示対象のタスク一覧
   */
  get displayTasks(): Task[] {
    // 表示モードに応じてタスクをフィルタリング
    const filteredTasks = this.showAllTasks ? this.tasks : this.tasks.filter(task => task.status === 0);
    
    // ステータスの昇順、作成日時の降順でソート
    return filteredTasks.sort((a, b) => {
      // まずステータスで比較
      if (a.status !== b.status) {
        return a.status - b.status;
      }
      // ステータスが同じ場合は作成日時で比較
      const dateA = new Date(a.created_at).getTime();
      const dateB = new Date(b.created_at).getTime();
      return dateB - dateA;
    });
  }

  /**
   * タスク一覧の表示モードを切り替えます。
   * 全タスク表示と未完了タスク表示を切り替えることができます。
   */
  toggleViewMode() {
    if (!this.isEnabled) return;
    this.showAllTasks = !this.showAllTasks;
  }

  /**
   * 新規タスク追加用のモーダルを開きます。
   * モーダル表示後、タイトル入力フィールドにフォーカスを移動します。
   */
  openAddTaskModal() {
    if (!this.isEnabled || this.showModal || this.isSavingTask) return;
    this.editingTask = null;
    this.taskForm = {
      title: '',
      dueDate: undefined,
      category: undefined
    };
    this.showModal = true;
    // モーダルが表示された後にフォーカスを移動
    setTimeout(() => {
      const titleInput = document.querySelector('input[name="title"]') as HTMLInputElement;
      if (titleInput) {
        titleInput.focus();
      }
    }, 100);
  }

  /**
   * 経験値更新モーダルを開き、完了済みタスクの経験値を獲得します。
   * 経験値獲得後、ストーリーが生成され、シーズン情報が更新されます。
   */
  updateExperience() {
    if (!this.isEnabled || this.isUpdatingExperience) {
      return;
    }

    // 経験値として獲得可能なタスクが存在するかチェック
    const hasEligibleTasks = this.tasks.some(task => 
      task.status === TaskStatus.COMPLETED && !task.experienced_at
    );

    if (!hasEligibleTasks) {
      this.showHoverMessage('完了したタスクがありません');
      return;
    }

    this.isUpdatingExperience = true;
    this.storyLoading.emit(true);

    // デスクトップ表示の場合、updateUserExperience()実行前に最新シーズンを選択
    if (!this.isMobile) {
      const dashboardData = this.dashboardService.getCurrentDashboardData();
      if (dashboardData && dashboardData.seasons) {
        const currentSeason = dashboardData.seasons.find(s => s.current_phase !== 4);
        if (currentSeason) {
          this.seasonSelected.emit(currentSeason.id);
        }
      }
    }

    // 経験値更新APIを呼び出す
    this.taskService.updateUserExperience().subscribe({
      next: (response) => {
        if (response.earned_exp === 0) {
          this.showHoverMessage('経験値は獲得できませんでした');
          this.isUpdatingExperience = false;
          this.storyLoading.emit(false);
          return;
        }
        
        // ダッシュボードデータを取得
        const dashboardData = this.dashboardService.getCurrentDashboardData();
        if (!dashboardData) {
          this.isUpdatingExperience = false;
          this.storyLoading.emit(false);
          return;
        }

        // シーズンの取得
        const seasonIndex = dashboardData.seasons.findIndex((s: Season) => s.id === response.season.id);
        if (seasonIndex !== -1) {
          // 既存のシーズンを更新
          const existingStories = dashboardData.seasons[seasonIndex].stories || [];
          dashboardData.seasons[seasonIndex] = {
            ...response.season,
            stories: existingStories
          };
        }

        if (response.new_season) {
          // 新しいシーズンを先頭に追加
          dashboardData.seasons.unshift(response.new_season);
        }

        // ストーリーの追加
        const currentSeason = dashboardData.seasons.find((s: Season) => s.id === response.season.id);
        
        // 完了済みで経験値未獲得のタスクを現在時刻で更新
        const now = new Date();
        this.tasks = this.tasks.map(task => {
          if (task.status === TaskStatus.COMPLETED && !task.experienced_at) {
            return { ...task, experienced_at: now };
          }
          return task;
        });
        
        if (currentSeason) {
          if (!currentSeason.stories) {
            currentSeason.stories = [];
          }
          currentSeason.stories.unshift(response.story);
        }

        // ユーザーデータの更新
        dashboardData.user = response.user;

        // タスクリストを更新
        dashboardData.tasks = this.tasks;

        // ダッシュボードデータを更新
        this.dashboardService.updateDashboardData(dashboardData);

        // タスク更新イベントを発火して、親コンポーネントに通知
        this.taskUpdated.emit();

        // ストーリー更新イベントを発火
        this.storyUpdated.emit();

        // デスクトップ表示の場合のみストーリータブに遷移
        if (!this.isMobile) {
          this.isUpdatingExperience = false;
          this.storyLoading.emit(false);
        } else {
          this.isUpdatingExperience = false;
          this.storyLoading.emit(false);
        }
      },
      error: (error) => {
        console.error('経験値更新エラー:', error);
        this.isUpdatingExperience = false;
        this.storyLoading.emit(false);
        
        // 500エラーの場合は特定のメッセージを表示
        if (error.status === 500) {
          this.showHoverMessage('物語の生成に失敗しました。再実行してください');
        }
      }
    });
  }

  /**
   * ホバーメッセージを表示します。
   * @param message 表示するメッセージ
   */
  private showHoverMessage(message: string) {
    const hoverMessage = document.createElement('div');
    hoverMessage.textContent = message;
    hoverMessage.style.position = 'fixed';
    hoverMessage.style.top = '50%';
    hoverMessage.style.left = '50%';
    hoverMessage.style.transform = 'translate(-50%, -50%)';
    hoverMessage.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
    hoverMessage.style.color = 'white';
    hoverMessage.style.padding = '1rem 2rem';
    hoverMessage.style.borderRadius = '0.5rem';
    hoverMessage.style.zIndex = '1000';
    document.body.appendChild(hoverMessage);

    setTimeout(() => {
      document.body.removeChild(hoverMessage);
    }, 3000);
  }

  /**
   * 既存タスクの編集用モーダルを開きます。
   * @param task 編集対象のタスク
   */
  editTask(task: Task) {
    if (!this.isEnabled || this.isSavingTask) {
      return;
    }
    
    if (this.showModal) {
      return;
    }
    
    this.editingTask = task;
    this.taskForm = {
      title: task.title,
      dueDate: task.due_date ? new Date(task.due_date).toISOString().split('T')[0] : undefined,
      category: task.category
    };
    this.showModal = true;
  }

  /**
   * モーダルを閉じ、フォームをリセットします。
   */
  closeModal() {
    this.showModal = false;
    this.editingTask = null;
    this.taskForm = {
      title: '',
      dueDate: undefined,
      category: undefined
    };
  }

  /**
   * タスクを保存します。
   * 新規作成と更新の両方に対応し、APIを通じてデータを保存します。
   */
  saveTask() {
    if (!this.isEnabled || !this.showModal) {
      return;
    }

    if (this.taskForm.title.length === 0) {
      return;
    }

    // 保存処理開始
    this.isSavingTask = true;

    const taskData = {
      title: this.taskForm.title,
      due_date: this.taskForm.dueDate ? new Date(this.taskForm.dueDate) : undefined,
      status: this.editingTask?.status || TaskStatus.PENDING,
      created_at: this.editingTask?.created_at || new Date().toISOString(),
      category: this.taskForm.category
    } as const;

    if (this.editingTask?.id) {
      // 既存タスクの更新は従来通りAPIレスポンスを待つ
      this.updateExistingTask(taskData);
    } else {
      // 新規タスク作成は即座にローカルに追加
      this.createNewTask(taskData);
      // モーダルは即座に閉じる（createNewTask内でcloseModal()が呼ばれる）
    }
  }

  /**
   * 既存のタスクを更新します。
   * @param taskData 更新するタスクデータ
   */
  private updateExistingTask(taskData: { title: string; due_date?: Date; status: TaskStatus; category: number | undefined }) {
    if (!this.editingTask?.id) return;

    this.taskService.updateTask(this.editingTask.id, taskData).subscribe({
      next: (updatedTask) => {
        const index = this.tasks.findIndex(t => t.id === updatedTask.id);
        if (index !== -1) {
          this.tasks[index] = updatedTask;
        }
        this.taskUpdated.emit();
        this.closeModal();
        this.isSavingTask = false;
      },
      error: (error) => {
        console.error('タスクの更新に失敗しました:', error);
        // エラー時はモーダルを再度開く
        this.showModal = true;
        this.isSavingTask = false;
      }
    });
  }

  /**
   * 新しいタスクを作成します。
   * APIレスポンスを待たずにローカルで追加し、バックグラウンドで更新します。
   * @param taskData 作成するタスクデータ
   */
  private createNewTask(taskData: { title: string; due_date?: Date; status: TaskStatus; category: number | undefined }) {
    // 1. 即座にローカルに追加
    const localTask: Task = {
      ...taskData,
      id: `temp_${Date.now()}`, // 一時的なID
      category: taskData.category, // ユーザーが選択したカテゴリーを保持
      created_at: new Date(),
      status: TaskStatus.PENDING
    };
    
    this.tasks = [localTask, ...this.tasks];
    
    // ダッシュボードデータを取得して更新
    const dashboardData = this.dashboardService.getCurrentDashboardData();
    if (dashboardData) {
      dashboardData.tasks = this.tasks;
      this.dashboardService.updateDashboardData(dashboardData);
    }
    
    // タスク更新イベントを発火
    this.taskUpdated.emit();
    this.closeModal();
    this.isSavingTask = false;
    
    // 2. バックグラウンドでAPI呼び出し
    this.taskService.createTask(taskData).subscribe({
      next: (serverTask) => {        
        // 3. サーバーレスポンスでローカルデータを更新
        const index = this.tasks.findIndex(t => t.id === localTask.id);
        if (index !== -1) {
          this.tasks[index] = serverTask;
          
          // ダッシュボードデータを更新
          if (dashboardData) {
            dashboardData.tasks = this.tasks;
            this.dashboardService.updateDashboardData(dashboardData);
          }
          
          // タスク更新イベントを発火
          this.taskUpdated.emit();
        }
      },
      error: (error) => {
        console.error('タスクの作成に失敗しました:', error);
        
        // エラー時はローカルタスクを削除
        this.tasks = this.tasks.filter(t => t.id !== localTask.id);
        
        // ダッシュボードデータを更新
        if (dashboardData) {
          dashboardData.tasks = this.tasks;
          this.dashboardService.updateDashboardData(dashboardData);
        }
        
        // タスク更新イベントを発火
        this.taskUpdated.emit();
        
        // エラーメッセージを表示
        this.showHoverMessage('タスクの作成に失敗しました');
      }
    });
  }

  /**
   * タスクの完了状態を切り替えます。
   * APIを通じてタスクのステータスを更新します。
   * @param task ステータスを更新するタスク
   */
  toggleTask(task: Task) {
    if (!this.isEnabled) {
      return;
    }

    if (!task.id) {
      return;
    }

    const newStatus = task.status === TaskStatus.PENDING ? TaskStatus.COMPLETED : TaskStatus.PENDING;
    this.taskService.updateTaskStatus(task.id, newStatus).subscribe({
      next: (updatedTask) => {
        // タスクの状態を更新
        const index = this.tasks.findIndex(t => t.id === task.id);
        if (index !== -1) {
          this.tasks[index] = updatedTask;
        }
        this.taskUpdated.emit();
      },
      error: (error) => {
        console.error('タスクのステータス更新に失敗しました:', error);
      }
    });
  }

  /**
   * タスクの削除確認モーダルを表示します。
   * @param task 削除対象のタスク
   */
  deleteTask(task: Task) {
    if (!this.isEnabled) {
      return;
    }

    if (!task.id) {
      return;
    }

    this.taskToDelete = task;
    this.showDeleteConfirm = true;
  }

  /**
   * 削除をキャンセルし、確認モーダルを閉じます。
   */
  cancelDelete() {
    this.showDeleteConfirm = false;
    this.taskToDelete = null;
  }

  /**
   * タスクの削除を実行します。
   * APIを通じてタスクを削除し、成功時は一覧からも削除します。
   */
  confirmDelete() {
    if (!this.taskToDelete?.id) return;

    this.taskService.deleteTask(this.taskToDelete.id).subscribe({
      next: () => {
        this.tasks = this.tasks.filter(t => t.id !== this.taskToDelete?.id);
        
        // ダッシュボードデータを取得して更新
        const dashboardData = this.dashboardService.getCurrentDashboardData();
        if (dashboardData) {
          // タスクリストを更新
          dashboardData.tasks = this.tasks;
          
          // ダッシュボードデータを更新
          this.dashboardService.updateDashboardData(dashboardData);
        }
        
        this.taskUpdated.emit();
        this.showDeleteConfirm = false;
        this.taskToDelete = null;
      },
      error: (error) => {
        console.error('タスクの削除に失敗しました:', error);
      }
    });
  }
} 