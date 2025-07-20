import { Routes } from '@angular/router';
import { SopFormComponent } from './sop-form/sop-form.component';
import { ChatInterfaceComponent } from './chat-interface/chat-interface.component';
import { ModelTrainingComponent } from './components/portal/model-training/model-training.component';

export const routes: Routes = [
  { path: '', component: ChatInterfaceComponent },
  { path: 'form', component: SopFormComponent },
  { path: 'training', component: ModelTrainingComponent },
  { path: 'portal/model-training', component: ModelTrainingComponent },
];
