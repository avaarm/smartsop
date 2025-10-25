import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { ElnService, Project, TeamMember, Experiment } from '../../../../services/eln-service.service';
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
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';

@Component({
  selector: 'app-project-detail',
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
    MatTableModule,
    MatChipsModule,
    MatDialogModule
  ],
  providers: [MatSnackBar],
  templateUrl: './project-detail.component.html',
  styleUrls: ['./project-detail.component.scss']
})
export class ProjectDetailComponent implements OnInit {
  projectId: string | null = null;
  project: Project | null = null;
  teamMembers: TeamMember[] = [];
  experiments: Experiment[] = [];
  projectForm: FormGroup;
  isNewProject = false;
  loading = true;
  saving = false;
  error = '';
  editMode = false;
  
  experimentDisplayedColumns: string[] = ['name', 'status', 'created_at', 'actions'];

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private elnService: ElnService,
    private fb: FormBuilder,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {
    this.projectForm = this.fb.group({
      name: ['', [Validators.required]],
      description: ['', [Validators.required]],
      status: ['active', [Validators.required]],
      start_date: [null],
      end_date: [null]
    });
  }

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      this.projectId = params.get('id');
      
      if (this.projectId === 'new') {
        this.isNewProject = true;
        this.editMode = true;
        this.loading = false;
      } else if (this.projectId) {
        this.loadProject();
      }
    });
  }

  loadProject(): void {
    if (!this.projectId) return;
    
    this.loading = true;
    this.elnService.getProject(this.projectId).subscribe({
      next: (response) => {
        if (response.success && response.project) {
          this.project = response.project;
          this.populateForm();
          this.loadTeamMembers();
          this.loadExperiments();
        } else {
          this.error = response.error || 'Failed to load project';
        }
        this.loading = false;
      },
      error: (err) => {
        this.error = err.message || 'Failed to load project';
        this.loading = false;
      }
    });
  }

  loadTeamMembers(): void {
    if (!this.projectId) return;
    
    this.elnService.getProjectTeamMembers(this.projectId).subscribe({
      next: (response) => {
        if (response.success && response.project?.team_members) {
          this.teamMembers = response.project.team_members;
        }
      },
      error: (err) => {
        console.error('Failed to load team members:', err);
      }
    });
  }

  loadExperiments(): void {
    if (!this.projectId) return;
    
    this.elnService.getExperiments(this.projectId).subscribe({
      next: (response) => {
        if (response.success && response.experiments) {
          this.experiments = response.experiments;
        }
      },
      error: (err) => {
        console.error('Failed to load experiments:', err);
      }
    });
  }

  populateForm(): void {
    if (!this.project) return;
    
    this.projectForm.patchValue({
      name: this.project.name,
      description: this.project.description,
      status: this.project.status,
      start_date: this.project.start_date ? new Date(this.project.start_date) : null,
      end_date: this.project.end_date ? new Date(this.project.end_date) : null
    });
  }

  toggleEditMode(): void {
    this.editMode = !this.editMode;
    if (!this.editMode) {
      this.populateForm();
    }
  }

  saveProject(): void {
    if (this.projectForm.invalid) {
      this.projectForm.markAllAsTouched();
      return;
    }
    
    const projectData = {
      ...this.projectForm.value,
      start_date: this.projectForm.value.start_date ? this.formatDate(this.projectForm.value.start_date) : null,
      end_date: this.projectForm.value.end_date ? this.formatDate(this.projectForm.value.end_date) : null
    };
    
    this.saving = true;
    
    if (this.isNewProject) {
      this.elnService.createProject(projectData).subscribe({
        next: (response) => {
          if (response.success && response.project) {
            this.snackBar.open('Project created successfully', 'Close', {
              duration: 3000
            });
            this.router.navigate(['/eln/projects', response.project.id]);
          } else {
            this.snackBar.open(response.error || 'Failed to create project', 'Close', {
              duration: 5000
            });
          }
          this.saving = false;
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to create project', 'Close', {
            duration: 5000
          });
          this.saving = false;
        }
      });
    } else if (this.projectId) {
      this.elnService.updateProject(this.projectId, projectData).subscribe({
        next: (response) => {
          if (response.success && response.project) {
            this.project = response.project;
            this.editMode = false;
            this.snackBar.open('Project updated successfully', 'Close', {
              duration: 3000
            });
          } else {
            this.snackBar.open(response.error || 'Failed to update project', 'Close', {
              duration: 5000
            });
          }
          this.saving = false;
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to update project', 'Close', {
            duration: 5000
          });
          this.saving = false;
        }
      });
    }
  }

  formatDate(date: Date): string {
    return date.toISOString().split('T')[0];
  }

  createExperiment(): void {
    this.router.navigate(['/eln/experiments/new'], {
      queryParams: { projectId: this.projectId }
    });
  }

  removeTeamMember(userId: string): void {
    if (!this.projectId) return;
    
    if (confirm('Are you sure you want to remove this team member?')) {
      this.elnService.removeProjectTeamMember(this.projectId, userId).subscribe({
        next: (response) => {
          if (response.success) {
            this.teamMembers = this.teamMembers.filter(member => member.user_id !== userId);
            this.snackBar.open('Team member removed successfully', 'Close', {
              duration: 3000
            });
          } else {
            this.snackBar.open(response.error || 'Failed to remove team member', 'Close', {
              duration: 5000
            });
          }
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to remove team member', 'Close', {
            duration: 5000
          });
        }
      });
    }
  }

  getStatusClass(status: string): string {
    switch (status.toLowerCase()) {
      case 'active':
        return 'status-active';
      case 'completed':
        return 'status-completed';
      case 'on hold':
        return 'status-on-hold';
      case 'in progress':
        return 'status-active';
      case 'planned':
        return 'status-planned';
      default:
        return 'status-default';
    }
  }
}
