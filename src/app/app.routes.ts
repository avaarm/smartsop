import { Routes } from '@angular/router';
import { MainLayoutComponent } from './components/layout/main-layout.component';

export const routes: Routes = [
  {
    path: '',
    component: MainLayoutComponent,
    children: [
      { path: '', redirectTo: 'gmp', pathMatch: 'full' },
      {
        path: 'gmp',
        loadComponent: () =>
          import('./components/gmp-docs/document-builder/document-builder.component')
            .then(m => m.DocumentBuilderComponent),
      },
    ],
  },
];
