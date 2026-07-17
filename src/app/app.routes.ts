import { Routes } from '@angular/router';
import { MainLayoutComponent } from './components/layout/main-layout.component';
import { authGuard } from './guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () =>
      import('./components/auth/login.component').then(m => m.LoginComponent),
  },
  {
    path: '',
    component: MainLayoutComponent,
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'gmp', pathMatch: 'full' },
      {
        path: 'gmp',
        loadComponent: () =>
          import('./components/gmp-docs/document-builder/document-builder.component')
            .then(m => m.DocumentBuilderComponent),
      },
      {
        path: 'protocols',
        loadComponent: () =>
          import('./components/protocols/protocol-list/protocol-list.component')
            .then(m => m.ProtocolListComponent),
      },
      {
        path: 'protocols/:id',
        loadComponent: () =>
          import('./components/protocols/protocol-detail/protocol-detail.component')
            .then(m => m.ProtocolDetailComponent),
      },
      {
        path: 'protocols/:id/run',
        loadComponent: () =>
          import('./components/protocols/protocol-run/protocol-run.component')
            .then(m => m.ProtocolRunComponent),
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
