import { Pipe, PipeTransform } from '@angular/core';

/**
 * 日付フォーマットパイプ
 * 
 * 日付を「月日」形式（例：3月15日）に変換します。
 * 入力値が無効な場合は空文字を返します。
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
   * @returns フォーマットされた日付文字列（例：「3月15日」）。無効な値の場合は空文字
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