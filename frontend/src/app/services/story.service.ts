import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Story } from '../models/types';
import { environment } from '../../environments/environment';

/**
 * ストーリーサービス
 * 
 * このサービスは以下の機能を提供します：
 * - シーズンごとのストーリー一覧の取得
 * - ストーリーに関連する画像URLの取得
 * 
 * ストーリーは物語の進行に応じて生成され、ユーザーの成長を記録します。
 */
@Injectable({
  providedIn: 'root'
})
export class StoryService {
  /** APIのベースURL */
  private apiUrl = `${environment.apiUrl}/users/me/seasons`;

  constructor(private http: HttpClient) {}

  /**
   * 指定されたシーズンのストーリー一覧を取得します。
   * @param seasonId シーズンID
   * @returns ストーリー一覧のObservable
   */
  getStories(seasonId: string): Observable<Story[]> {
    return this.http.get<Story[]>(`${this.apiUrl}/${seasonId}/stories`);
  }

  /**
   * 指定されたストーリーの画像URLを取得します。
   * @param seasonId シーズンID
   * @param storyId ストーリーID
   * @returns ストーリー画像のURLのObservable
   */
  getStoryImage(seasonId: string, storyId: string): Observable<{ url: string }> {
    return this.http.get<{ url: string }>(`${this.apiUrl}/${seasonId}/story-image-url`);
  }
} 