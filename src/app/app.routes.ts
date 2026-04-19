import { Routes } from '@angular/router';
import { MainLayoutComponent } from './components/layout/main-layout.component';

export const routes: Routes = [
  {
    path: '',
    component: MainLayoutComponent,
    children: [
      // Protocol Knowledge is the primary landing experience
      { path: '', redirectTo: 'protocols', pathMatch: 'full' },
      {
        path: 'protocols',
        loadComponent: () =>
          import('./components/gmp-docs/protocols/protocols.component')
            .then(m => m.ProtocolsComponent),
      },
      {
        path: 'gmp',
        loadComponent: () =>
          import('./components/gmp-docs/document-builder/document-builder.component')
            .then(m => m.DocumentBuilderComponent),
      },
      {
        path: 'account',
        loadComponent: () =>
          import('./components/gmp-docs/account-settings/account-settings.component')
            .then(m => m.AccountSettingsComponent),
      },
    ],
  },
];
