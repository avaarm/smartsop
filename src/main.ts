import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';

// Use the shared appConfig so the browser gets the same providers as SSR —
// crucially the auth HTTP interceptor and client hydration. (Bootstrapping
// with a separate inline config here silently dropped both on the client.)
bootstrapApplication(AppComponent, appConfig)
  .catch(err => console.error(err));
