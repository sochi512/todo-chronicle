import { Component, Input, OnChanges, SimpleChanges, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Season, Story, StoryPhase } from '../../models/types';
import { StoryService } from '../../services/story.service';

/**
 * ストーリーコンポーネント
 * シーズンのストーリーを表示し、現在のストーリーと履歴の切り替えを管理します。
 * ストーリーの生成状態に応じてローディングアニメーションを表示します。
 */
@Component({
  selector: 'app-story',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './story.component.html',
  styleUrls: ['./story.component.scss']
})
export class StoryComponent implements OnChanges {
  /** シーズン一覧 */
  @Input() seasons: Season[] = [];
  /** コンポーネントの有効/無効状態 */
  @Input() isEnabled = true;
  /** 選択中のシーズンID */
  @Input() selectedSeasonId?: string;
  /** ストーリー一覧 */
  @Input() stories: Story[] = [];
  /** ローディング状態 */
  @Input() isLoading = false;
  /** モバイル表示フラグ */
  @Input() isMobile = false;
  /** 外部から制御するビュー状態 */
  @Input() currentView?: 'current' | 'history';
  /** 外部から制御する選択中のストーリーシーズンID */
  @Input() selectedStorySeasonId?: string;
  /** ビュー変更イベント */
  @Output() viewChanged = new EventEmitter<'current' | 'history'>();
  /** シーズン選択イベント */
  @Output() seasonSelected = new EventEmitter<string>();
  /** 現在のビュー（現在/履歴） */
  _currentView: 'current' | 'history' = 'current';
  /** 選択中のシーズン */
  selectedSeason: Season | null = null;
  /** 初期ロード状態 */
  isInitialLoad = true;
  /** ストーリーフェーズ（テンプレート用） */
  StoryPhase = StoryPhase;
  /** ローディングアニメーションのステップ */
  loadingStep = 0;
  /** ローディングアニメーションのインターバル */
  private loadingInterval: any;
  /** 拡大表示中の画像URL */
  selectedImageUrl: string | null = null;

  /** ローディングアニメーションの定数 */
  private readonly LOADING_INTERVAL_MS = 1800;  // 1ステップあたりの待機時間（ミリ秒）
  private readonly MAX_LOADING_STEPS = 20;      // 最大リトライ回数（30秒 ÷ 1.5秒 = 20回）

  /** 画像取得のリトライ回数 */
  private imageRetryCount = 0;
  /** 画像取得のリトライタイマー */
  private imageRetryTimeout: any;

  constructor(private storyService: StoryService) {
    setTimeout(() => {
      this.isInitialLoad = false;
    }, 100);
  }

  /**
   * 入力プロパティの変更を監視し、必要な処理を実行します。
   * @param changes 変更されたプロパティの情報
   */
  ngOnChanges(changes: SimpleChanges) {
    // 外部から制御されるビュー状態の同期
    if (this.currentView) {
      this._currentView = this.currentView;
    }

    // 外部から制御される選択中のストーリーシーズンIDの処理
    if (changes['selectedStorySeasonId'] && this.selectedStorySeasonId) {
      const season = this.seasons.find(s => s.id === this.selectedStorySeasonId);
      if (season) {
        this.selectedSeason = season;
        // ストーリーが未取得の場合は取得
        if (season.current_chapter !== 0 && (!season.stories || season.stories.length === 0)) {
          this.loadStories(season);
        }
        // 完了フェーズの場合は画像URLを取得
        if (season.current_phase === StoryPhase.KAN) {
          this.loadStoryImages(season);
        }
      }
    }

    if (changes['seasons'] || changes['selectedSeasonId'] || changes['stories']) {
      // シーズン一覧が空になった場合、選択状態をリセット
      if (!this.seasons.length) {
        this.resetState();
        return;
      }

      // selectedSeasonIdの変更を処理（頁をめくるボタンクリック時）
      if (changes['selectedSeasonId'] && this.selectedSeasonId) {
        const season = this.seasons.find(s => s.id === this.selectedSeasonId);
        if (season) {
          this.selectedSeason = season;
          // ストーリーが未取得の場合は取得
          if (season.current_chapter !== 0 && (!season.stories || season.stories.length === 0)) {
            this.loadStories(season);
          }
          // 完了フェーズの場合は画像URLを取得
          if (season.current_phase === StoryPhase.KAN) {
            this.loadStoryImages(season);
          }
        }
      }
    }
    if (changes['isLoading']) {
      if (this.isLoading) {
        this.startLoadingAnimation();
      } else {
        this.stopLoadingAnimation();
      }
    }
  }

  /**
   * 現在表示中のシーズンを取得します。
   * 優先順位：頁をめくるボタンクリック時 > 履歴タブでの選択 > 選択中のシーズン > 進行中のシーズン
   */
  get currentSeason(): Season | undefined {
    // 1. selectedStorySeasonIdがあれば最優先（履歴タブでの選択）
    if (this.selectedStorySeasonId) {
      const season = this.seasons.find(s => s.id === this.selectedStorySeasonId);
      if (season) return season;
    }
    // 2. selectedSeasonIdがあれば次に優先（頁をめくるボタンクリック時）
    if (this.selectedSeasonId) {
      const season = this.seasons.find(s => s.id === this.selectedSeasonId);
      if (season) return season;
    }
    // 3. 履歴タブで選択中の場合は、selectedSeasonを優先
    if (this._currentView === 'history' && this.selectedSeason) {
      return this.selectedSeason;
    }
    // 4. 次にselectedSeasonを確認
    if (this.selectedSeason) {
      return this.selectedSeason;
    }
    // 5. デフォルト：進行中のシーズンを表示
    return this.seasons.find(s => s.current_phase !== 4);
  }

  /**
   * 現在のストーリービューに切り替えます。
   */
  switchToCurrentView() {
    this._currentView = 'current';
    this.viewChanged.emit('current');
  }

  /**
   * 履歴ビューに切り替えます。
   */
  switchToHistoryView() {
    this._currentView = 'history';
    this.viewChanged.emit('history');
  }

  /**
   * シーズンを選択し、関連するストーリーを読み込みます。
   * @param season 選択するシーズン
   */
  selectSeason(season: Season) {
    if (!this.isEnabled || this.isInitialLoad) return;

    if (season.current_chapter !== 0 && (!season.stories || season.stories.length === 0)) {
      this.loadStories(season);
    } else {
      this.selectedSeason = season;
      // 履歴タブでの選択時は、currentタブに切り替える
      this._currentView = 'current';
      this.viewChanged.emit('current');
      this.seasonSelected.emit(season.id!);
      // 完了フェーズの場合は画像URLを取得
      if (season.current_phase === StoryPhase.KAN) {
        this.loadStoryImages(season);
      }
    }
  }

  /**
   * 選択したシーズンのストーリーを読み込みます。
   * @param season ストーリーを読み込むシーズン
   */
  private loadStories(season: Season) {
    this.storyService.getStories(season.id!).subscribe({
      next: (stories: Story[] | { stories: Story[] }) => {
        season.stories = Array.isArray(stories) ? stories : stories.stories || [];
        this.selectedSeason = season;
        // 履歴タブでの選択時は、currentタブに切り替える
        this._currentView = 'current';
        this.viewChanged.emit('current');
        this.seasonSelected.emit(season.id!);
        // 完了フェーズの場合は画像URLを取得
        if (season.current_phase === StoryPhase.KAN) {
          this.loadStoryImages(season);
        }
      },
      error: (error) => {
        console.error('ストーリーの取得に失敗しました:', error);
        this.selectedSeason = season;
        // 履歴タブでの選択時は、currentタブに切り替える
        this._currentView = 'current';
        this.viewChanged.emit('current');
        this.seasonSelected.emit(season.id!);
      }
    });
  }

  /**
   * 完了フェーズのストーリー画像を読み込みます。
   * 画像取得に失敗した場合は一定間隔でリトライします。
   * @param season 画像を読み込むシーズン
   */
  private loadStoryImages(season: Season) {
    // シーズンが完了フェーズでない場合は処理をスキップ
    if (season.current_phase !== StoryPhase.KAN || !season.stories) return;

    // 完フェーズのストーリーを取得
    const completedStory = season.stories.find(story => story.phase === StoryPhase.KAN);
    if (!completedStory) return;

    // 画像URLを取得
    this.storyService.getStoryImage(season.id!, completedStory.id!).subscribe({
      next: (response) => {
        completedStory.imageUrl = response.url;
        // 成功したらリトライカウントをリセット
        this.imageRetryCount = 0;
        if (this.imageRetryTimeout) {
          clearTimeout(this.imageRetryTimeout);
          this.imageRetryTimeout = null;
        }
      },
      error: (error) => {
        console.error('ストーリー画像の取得に失敗しました:', error);
        
        // リトライ回数が上限に達していない場合は再試行
        if (this.imageRetryCount < this.MAX_LOADING_STEPS) {
          this.imageRetryCount++;
          console.log(`画像取得のリトライ ${this.imageRetryCount}/${this.MAX_LOADING_STEPS}`);
          
          // 一定時間後に再試行
          this.imageRetryTimeout = setTimeout(() => {
            this.loadStoryImages(season);
          }, this.LOADING_INTERVAL_MS);
        } else {
          console.error('画像取得の最大リトライ回数に達しました');
          this.imageRetryCount = 0;
        }
      }
    });
  }

  /**
   * コンポーネントの状態をリセットします。
   */
  private resetState() {
    this.selectedSeason = null;
    this._currentView = 'current';
    this.isInitialLoad = true;
    setTimeout(() => {
      this.isInitialLoad = false;
    }, 100);
  }

  /**
   * ローディングアニメーションを開始します。
   */
  private startLoadingAnimation() {
    this.loadingStep = 0;
    this.loadingInterval = setInterval(() => {
      if (this.loadingStep < this.MAX_LOADING_STEPS) {
        this.loadingStep++;
      } else {
        // 最大ステップ数に達したら、インターバルを停止
        clearInterval(this.loadingInterval);
        this.loadingInterval = null;
      }
    }, this.LOADING_INTERVAL_MS);
  }

  /**
   * ローディングアニメーションを停止します。
   */
  private stopLoadingAnimation() {
    if (this.loadingInterval) {
      clearInterval(this.loadingInterval);
      this.loadingInterval = null;
    }
    // ローディングが停止した時のみステップをリセット
    if (!this.isLoading) {
      this.loadingStep = 0;
    }
  }

  /**
   * コンポーネントの破棄時にタイマーをクリアします。
   */
  ngOnDestroy() {
    this.stopLoadingAnimation();
    // 画像取得のリトライタイマーをクリア
    if (this.imageRetryTimeout) {
      clearTimeout(this.imageRetryTimeout);
      this.imageRetryTimeout = null;
    }
  }

  /**
   * ストーリーの内容をフォーマットし、完了タスクの変換テキストをハイライト表示します。
   * @param story ストーリーオブジェクト
   * @returns フォーマットされたHTML文字列
   */
  formatStoryContent(story: Story): string {
    if (!story.completed_tasks || story.completed_tasks.length === 0) {
      return story.content;
    }

    let formattedContent = story.content;
    
    // 完了タスクの変換テキストを処理
    story.completed_tasks.forEach(task => {
      const converted = task['converted'];
      const original = task['original'];
      
      if (converted && original) {
        // 正規表現でエスケープ
        const escapedConverted = converted.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(escapedConverted, 'g');
        
        // 変換テキストをハイライト表示に置換
        formattedContent = formattedContent.replace(
          regex,
          `<span class="highlight-text">${converted}<span class="tooltip">${original}</span></span>`
        );
      }
    });

    return formattedContent;
  }

  /**
   * 画像を拡大表示します。
   * @param imageUrl 拡大表示する画像のURL
   */
  openImageModal(imageUrl: string) {
    this.selectedImageUrl = imageUrl;
  }

  /**
   * 画像の拡大表示を閉じます。
   */
  closeImageModal() {
    this.selectedImageUrl = null;
  }

  /**
   * ストーリーの洞察から名前部分を取得します。
   * @param insight 洞察テキスト
   * @returns 名前部分
   */
  getInsightName(insight: string): string {
    if (!insight) return '';
    const lines = insight.split('\n');
    return lines[0] || '';
  }

  /**
   * ストーリーの洞察から内容部分を取得します。
   * @param insight 洞察テキスト
   * @returns 内容部分（最初の改行以降）
   */
  getInsightContent(insight: string): string {
    if (!insight) return '';
    const lines = insight.split('\n');
    return lines.slice(1).join('\n');
  }

  /**
   * ストーリーコンテンツをフォーマットします。
   */
} 