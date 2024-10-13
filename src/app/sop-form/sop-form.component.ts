import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';  // Required for common Angular directives like *ngIf

@Component({
  selector: 'app-sop-form',
  standalone: true,
  imports: [FormsModule, CommonModule],  // Make sure to import FormsModule and CommonModule
  templateUrl: './sop-form.component.html',
})
export class SopFormComponent {
  formData = { steps: '', roles: '' };
  sopContent: string = '';
  errorMessage: string = '';
  loading: boolean = false;

  constructor() {}

  onSubmit() {
    this.errorMessage = '';
    this.sopContent = '';
    this.loading = true;

    // Implement the form submission logic here
  }
}







