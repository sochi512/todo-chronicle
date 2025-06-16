import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';
import { FormsModule } from '@angular/forms'; // 追加
import { provideAnimations } from '@angular/platform-browser/animations';
import { isDevMode } from '@angular/core';

if (isDevMode()) {
  console.log('Running in development mode');
}

bootstrapApplication(AppComponent, {
  providers: [
    ...appConfig.providers,
    provideAnimations()
  ]
}).catch(err => {
  console.error('Application bootstrap error:', err);
  // エラーの詳細を表示
  if (err instanceof Error) {
    console.error('Error name:', err.name);
    console.error('Error message:', err.message);
    console.error('Error stack:', err.stack);
  }
});
