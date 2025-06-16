import { Pipe, PipeTransform } from '@angular/core';

/**
 * 日付を「月日」形式にフォーマットするパイプ
 * 
 * このパイプは以下の機能を提供します：
 * - 日付文字列またはDateオブジェクトを「月日」形式に変換
 * - 無効な日付の場合は空文字列を返す
 * - 未定義の値の場合は空文字列を返す
 * 
 * 使用例：
 * ```html
 * {{ task.due_date | dateFormat }}  <!-- 例: 5月15日 -->
 * ```
 */
@Pipe({
  name: 'dateFormat',
  standalone: true
})
export class DateFormatPipe implements PipeTransform {
  /**
   * 日付を「月日」形式に変換します。
   * 
   * @param value 変換対象の日付（文字列、Dateオブジェクト、またはundefined）
   * @returns フォーマットされた日付文字列（例: 5月15日）。無効な日付または未定義の場合は空文字列
   */
  transform(value: string | Date | undefined): string {
    if (!value) return '';
    
    const date = new Date(value);
    if (isNaN(date.getTime())) return '';
    
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    
    return `${month}月${day}日`;
  }
} 