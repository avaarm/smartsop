import { Routes } from '@angular/router';
import { SopFormComponent } from './sop-form/sop-form.component';
import { ChatInterfaceComponent } from './chat-interface/chat-interface.component';

export const routes: Routes = [
  { path: '', component: ChatInterfaceComponent },
  { path: 'form', component: SopFormComponent },
];
