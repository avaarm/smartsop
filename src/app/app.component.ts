import { Component } from '@angular/core';
import { SopFormComponent } from './sop-form/sop-form.component';  // Import the SopFormComponent

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  standalone: true,
  imports: [
    SopFormComponent  // Add SopFormComponent here
  ]
})
export class AppComponent {}
