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
    path: 'reset-password',
    loadComponent: () =>
      import('./components/auth/reset-password.component').then(m => m.ResetPasswordComponent),
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
        path: 'register',
        loadComponent: () =>
          import('./components/protocols/document-register/document-register.component')
            .then(m => m.DocumentRegisterComponent),
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
        path: 'assets',
        loadComponent: () =>
          import('./components/assets/asset-list/asset-list.component')
            .then(m => m.AssetListComponent),
      },
      {
        path: 'scan/:slug',
        loadComponent: () =>
          import('./components/assets/asset-scan/asset-scan.component')
            .then(m => m.AssetScanComponent),
      },
      {
        path: 'schedule',
        loadComponent: () =>
          import('./components/schedule/schedule.component')
            .then(m => m.ScheduleComponent),
      },
      {
        path: 'deviations',
        loadComponent: () =>
          import('./components/protocols/deviations/deviations.component')
            .then(m => m.DeviationsComponent),
      },
      {
        path: 'competency',
        loadComponent: () =>
          import('./components/competency/competency.component')
            .then(m => m.CompetencyComponent),
      },
      {
        path: 'analytics',
        loadComponent: () =>
          import('./components/protocols/analytics/analytics.component')
            .then(m => m.AnalyticsComponent),
      },
      {
        path: 'audit',
        loadComponent: () =>
          import('./components/audit/audit.component')
            .then(m => m.AuditComponent),
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
