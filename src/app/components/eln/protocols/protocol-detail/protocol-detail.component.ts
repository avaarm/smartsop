import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, FormArray, Validators, ReactiveFormsModule } from '@angular/forms';
import { ElnService, Protocol, ProtocolStep } from '../../../../services/eln-service.service';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatTabsModule } from '@angular/material/tabs';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatStepperModule } from '@angular/material/stepper';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatExpansionModule } from '@angular/material/expansion';
import { CdkDragDrop, moveItemInArray, DragDropModule } from '@angular/cdk/drag-drop';

@Component({
  selector: 'app-protocol-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    ReactiveFormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatSelectModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatTabsModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatStepperModule,
    MatChipsModule,
    MatDividerModule,
    MatTooltipModule,
    MatExpansionModule,
    DragDropModule
  ],
  providers: [MatSnackBar],
  templateUrl: './protocol-detail.component.html',
  styleUrls: ['./protocol-detail.component.scss']
})
export class ProtocolDetailComponent implements OnInit {
  protocolId: string | null = null;
  protocol: Protocol | null = null;
  protocolForm: FormGroup;
  isNewProtocol = false;
  loading = true;
  saving = false;
  error = '';
  editMode = false;
  
  // Project selection
  projects: { id: string, name: string }[] = [];
  selectedProjectId: string | null = null;
  
  // Step categories
  stepCategories: string[] = [
    'Preparation', 
    'Sample Collection', 
    'Processing', 
    'Analysis', 
    'Clean-up', 
    'Safety', 
    'Quality Control',
    'Other'
  ];

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private elnService: ElnService,
    private fb: FormBuilder,
    private snackBar: MatSnackBar
  ) {
    this.protocolForm = this.fb.group({
      name: ['', [Validators.required]],
      description: ['', [Validators.required]],
      project_id: [''],
      category: [''],
      version: [1.0],
      steps: this.fb.array([]),
      materials: [''],
      equipment: [''],
      safety_notes: [''],
      references: ['']
    });
  }

  ngOnInit(): void {
    this.loadProjects();
    
    this.route.paramMap.subscribe(params => {
      this.protocolId = params.get('id');
      
      if (this.protocolId === 'new') {
        this.isNewProtocol = true;
        this.editMode = true;
        this.loading = false;
        this.addStep(); // Add an initial empty step
        
        // Check if there's a project ID in the query params
        this.route.queryParams.subscribe(queryParams => {
          if (queryParams['projectId']) {
            this.selectedProjectId = queryParams['projectId'];
            this.protocolForm.patchValue({
              project_id: this.selectedProjectId
            });
          }
        });
      } else if (this.protocolId) {
        this.loadProtocol();
      }
    });
  }

  loadProtocol(): void {
    if (!this.protocolId) return;
    
    this.loading = true;
    this.elnService.getProtocol(this.protocolId).subscribe({
      next: (response) => {
        if (response.success && response.protocol) {
          this.protocol = response.protocol;
          this.selectedProjectId = this.protocol.project_id || null;
          this.populateForm();
        } else {
          this.error = response.error || 'Failed to load protocol';
        }
        this.loading = false;
      },
      error: (err) => {
        this.error = err.message || 'Failed to load protocol';
        this.loading = false;
      }
    });
  }

  loadProjects(): void {
    this.elnService.getProjects().subscribe({
      next: (response) => {
        if (response.success && response.projects) {
          this.projects = response.projects.map(project => ({
            id: project.id,
            name: project.name
          }));
        }
      },
      error: (err) => {
        console.error('Failed to load projects:', err);
      }
    });
  }

  populateForm(): void {
    if (!this.protocol) return;
    
    // Clear existing steps
    this.steps.clear();
    
    // Add steps from protocol
    if (this.protocol.steps && this.protocol.steps.length > 0) {
      this.protocol.steps.forEach(step => {
        this.steps.push(this.createStepFormGroup(step));
      });
    }
    
    // Populate other fields
    this.protocolForm.patchValue({
      name: this.protocol.name,
      description: this.protocol.description,
      project_id: this.protocol.project_id || '',
      category: this.protocol.category || '',
      version: this.protocol.version || 1.0,
      materials: this.protocol.materials || '',
      equipment: this.protocol.equipment || '',
      safety_notes: this.protocol.safety_notes || '',
      references: this.protocol.references || ''
    });
  }

  get steps(): FormArray {
    return this.protocolForm.get('steps') as FormArray;
  }

  createStepFormGroup(step?: ProtocolStep | any): FormGroup {
    return this.fb.group({
      title: [step?.title || step?.name || '', Validators.required],
      description: [step?.description || '', Validators.required],
      category: [step?.category || 'Other'],
      duration: [step?.duration || step?.duration_minutes || ''],
      temperature: [step?.temperature || ''],
      notes: [step?.notes || ''],
      warnings: [step?.warnings || '']
    });
  }

  addStep(): void {
    this.steps.push(this.createStepFormGroup());
  }

  removeStep(index: number): void {
    if (this.steps.length > 1 || confirm('Are you sure you want to remove the last step? This will leave the protocol without any steps.')) {
      this.steps.removeAt(index);
    }
  }

  moveStepUp(index: number): void {
    if (index > 0) {
      moveItemInArray(this.steps.controls, index, index - 1);
    }
  }

  moveStepDown(index: number): void {
    if (index < this.steps.length - 1) {
      moveItemInArray(this.steps.controls, index, index + 1);
    }
  }

  onStepDrop(event: CdkDragDrop<FormGroup[]>): void {
    moveItemInArray(this.steps.controls, event.previousIndex, event.currentIndex);
  }

  toggleEditMode(): void {
    this.editMode = !this.editMode;
    if (!this.editMode) {
      this.populateForm();
    }
  }

  saveProtocol(): void {
    if (this.protocolForm.invalid) {
      this.markFormGroupTouched(this.protocolForm);
      this.snackBar.open('Please fill in all required fields', 'Close', {
        duration: 5000
      });
      return;
    }
    
    const protocolData = this.protocolForm.value;
    
    this.saving = true;
    
    if (this.isNewProtocol) {
      this.elnService.createProtocol(protocolData).subscribe({
        next: (response) => {
          if (response.success && response.protocol) {
            this.snackBar.open('Protocol created successfully', 'Close', {
              duration: 3000
            });
            this.router.navigate(['/eln/protocols', response.protocol.id]);
          } else {
            this.snackBar.open(response.error || 'Failed to create protocol', 'Close', {
              duration: 5000
            });
          }
          this.saving = false;
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to create protocol', 'Close', {
            duration: 5000
          });
          this.saving = false;
        }
      });
    } else if (this.protocolId) {
      this.elnService.updateProtocol(this.protocolId, protocolData).subscribe({
        next: (response) => {
          if (response.success && response.protocol) {
            this.protocol = response.protocol;
            this.editMode = false;
            this.snackBar.open('Protocol updated successfully', 'Close', {
              duration: 3000
            });
          } else {
            this.snackBar.open(response.error || 'Failed to update protocol', 'Close', {
              duration: 5000
            });
          }
          this.saving = false;
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to update protocol', 'Close', {
            duration: 5000
          });
          this.saving = false;
        }
      });
    }
  }

  markFormGroupTouched(formGroup: FormGroup): void {
    Object.values(formGroup.controls).forEach(control => {
      control.markAsTouched();
      
      if (control instanceof FormGroup) {
        this.markFormGroupTouched(control);
      } else if (control instanceof FormArray) {
        for (const ctrl of control.controls) {
          if (ctrl instanceof FormGroup) {
            this.markFormGroupTouched(ctrl);
          } else {
            ctrl.markAsTouched();
          }
        }
      }
    });
  }

  createNewVersion(): void {
    if (!this.protocolId || !this.protocol) return;
    
    // TODO: Implement createProtocolVersion in ElnService
    this.snackBar.open('Version control feature coming soon', 'Close', {
      duration: 3000
    });
    
    /* if (confirm('Are you sure you want to create a new version of this protocol? This will create a copy with an incremented version number.')) {
      this.elnService.createProtocolVersion(this.protocolId).subscribe({
        next: (response: any) => {
          if (response.success && response.protocol) {
            this.snackBar.open('New protocol version created successfully', 'Close', {
              duration: 3000
            });
            this.router.navigate(['/eln/protocols', response.protocol.id]);
          } else {
            this.snackBar.open(response.error || 'Failed to create new version', 'Close', {
              duration: 5000
            });
          }
        },
        error: (err: any) => {
          this.snackBar.open(err.message || 'Failed to create new version', 'Close', {
            duration: 5000
          });
        }
      });
    } */
  }

  exportProtocol(): void {
    if (!this.protocolId) return;
    
    // TODO: Implement exportProtocol in ElnService
    this.snackBar.open('Export feature coming soon', 'Close', {
      duration: 3000
    });
    
    /* this.elnService.exportProtocol(this.protocolId).subscribe({
      next: (response: any) => {
        if (response.success && response.export_url) {
          window.open(response.export_url, '_blank');
        } else {
          this.snackBar.open(response.error || 'Failed to export protocol', 'Close', {
            duration: 5000
          });
        }
      },
      error: (err: any) => {
        this.snackBar.open(err.message || 'Failed to export protocol', 'Close', {
          duration: 5000
        });
      }
    }); */
  }

  getProjectName(projectId: string | undefined): string {
    if (!projectId) return 'Project';
    const project = this.projects.find(p => p.id === projectId);
    return project?.name || 'Project';
  }
}
