import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'lineBreaks',
  standalone: true
})
export class LineBreaksPipe implements PipeTransform {
  transform(value: string): string {
    if (!value) return '';
    return value.replace(/\n/g, '<br>');
  }
}
