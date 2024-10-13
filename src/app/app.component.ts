import { Component } from '@angular/core';
import { SopFormComponent } from './sop-form/sop-form.component';  // Import the standalone component

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  standalone: true,  // Mark as standalone
  imports: [SopFormComponent],  // Import SopFormComponent directly
})
export class AppComponent {}
