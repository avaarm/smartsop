import { Routes } from '@angular/router';
import { MainLayoutComponent } from './components/layout/main-layout.component';
import { SopFormComponent } from './sop-form/sop-form.component';
import { ChatInterfaceComponent } from './chat-interface/chat-interface.component';
import { ModelTrainingComponent } from './components/portal/model-training/model-training.component';

export const routes: Routes = [
  {
    path: '',
    component: MainLayoutComponent,
    children: [
      { path: '', component: ChatInterfaceComponent },
      { path: 'form', component: SopFormComponent },
      { path: 'training', component: ModelTrainingComponent },
      { path: 'portal/model-training', component: ModelTrainingComponent },
      
      // GMP Document Builder
      {
        path: 'gmp',
        children: [
          {
            path: '',
            loadComponent: () => import('./components/gmp-docs/document-list/document-list.component')
              .then(m => m.DocumentListComponent)
          },
          {
            path: 'new',
            loadComponent: () => import('./components/gmp-docs/document-builder/document-builder.component')
              .then(m => m.DocumentBuilderComponent)
          },
        ]
      },

      // ELN Module Routes
      {
        path: 'eln',
        children: [
          {
            path: 'dashboard',
            loadComponent: () => import('./components/eln/dashboard/dashboard.component')
              .then(m => m.DashboardComponent)
          },
          {
            path: 'projects',
            loadComponent: () => import('./components/eln/projects/project-list/project-list.component')
              .then(m => m.ProjectListComponent)
          },
          {
            path: 'projects/:id',
            loadComponent: () => import('./components/eln/projects/project-detail/project-detail.component')
              .then(m => m.ProjectDetailComponent)
          },
          {
            path: 'experiments',
            loadComponent: () => import('./components/eln/experiments/experiment-list/experiment-list.component')
              .then(m => m.ExperimentListComponent)
          },
          {
            path: 'experiments/:id',
            loadComponent: () => import('./components/eln/experiments/experiment-detail/experiment-detail.component')
              .then(m => m.ExperimentDetailComponent)
          },
          {
            path: 'protocols',
            loadComponent: () => import('./components/eln/protocols/protocol-list/protocol-list.component')
              .then(m => m.ProtocolListComponent)
          },
          {
            path: 'protocols/:id',
            loadComponent: () => import('./components/eln/protocols/protocol-detail/protocol-detail.component')
              .then(m => m.ProtocolDetailComponent)
          },
          {
            path: 'inventory',
            loadComponent: () => import('./components/eln/inventory/inventory-list/inventory-list.component')
              .then(m => m.InventoryListComponent)
          },
          {
            path: 'inventory/:id',
            loadComponent: () => import('./components/eln/inventory/inventory-detail/inventory-detail.component')
              .then(m => m.InventoryDetailComponent)
          },
          {
            path: 'users',
            loadComponent: () => import('./components/eln/users/user-list/user-list.component')
              .then(m => m.UserListComponent)
          },
          {
            path: 'users/:id',
            loadComponent: () => import('./components/eln/users/user-detail/user-detail.component')
              .then(m => m.UserDetailComponent)
          }
        ]
      }
    ]
  }
];
