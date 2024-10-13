import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';  // Import CommonModule for ngIf
import { FormsModule } from '@angular/forms';    // Import FormsModule for [(ngModel)]

@Component({
  selector: 'app-sop-form',
  standalone: true,  // Mark this as a standalone component
  imports: [CommonModule, FormsModule],  // Import CommonModule and FormsModule
  templateUrl: './sop-form.component.html',
})
export class SopFormComponent {
  formData = { steps: '', roles: '' };
  sopContent: string = '';

  constructor() {}

  onSubmit() {
    // Logic to handle form submission
  }
}





