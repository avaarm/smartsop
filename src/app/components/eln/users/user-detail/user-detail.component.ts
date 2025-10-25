import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { ElnService, User, Project } from '../../../../services/eln-service.service';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatChipsModule } from '@angular/material/chips';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSortModule } from '@angular/material/sort';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';

@Component({
  selector: 'app-user-detail',
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
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatChipsModule,
    MatTabsModule,
    MatTableModule,
    MatPaginatorModule,
    MatSortModule,
    MatTooltipModule,
    MatDividerModule
  ],
  providers: [MatSnackBar],
  templateUrl: './user-detail.component.html',
  styleUrls: ['./user-detail.component.scss']
})
export class UserDetailComponent implements OnInit {
  userId: string | null = null;
  user: User | null = null;
  userForm: FormGroup;
  isNewUser = false;
  loading = true;
  saving = false;
  error = '';
  editMode = false;
  currentUser: User | null = null;
  
  // For project assignment
  allProjects: Project[] = [];
  assignedProjects: Project[] = [];
  
  // Activity history
  activityHistory: any[] = [];
  displayedColumns: string[] = ['date', 'activity', 'details'];
  
  // Available roles
  roles: string[] = ['admin', 'manager', 'scientist', 'technician', 'viewer'];

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private elnService: ElnService,
    private fb: FormBuilder,
    private snackBar: MatSnackBar
  ) {
    this.userForm = this.fb.group({
      name: ['', [Validators.required]],
      email: ['', [Validators.required, Validators.email]],
      role: ['', [Validators.required]],
      department: [''],
      title: [''],
      phone: [''],
      status: ['active'],
      password: ['', [Validators.minLength(8)]],
      confirmPassword: ['']
    }, { validators: this.passwordMatchValidator });
  }

  ngOnInit(): void {
    this.loadCurrentUser();
    this.loadAllProjects();
    
    this.route.paramMap.subscribe(params => {
      this.userId = params.get('id');
      
      if (this.userId === 'new') {
        this.isNewUser = true;
        this.editMode = true;
        this.loading = false;
      } else if (this.userId) {
        this.loadUser();
      }
    });
  }

  loadCurrentUser(): void {
    this.elnService.getCurrentUser().subscribe({
      next: (response) => {
        if (response.success && response.user) {
          this.currentUser = response.user;
        }
      },
      error: (err) => {
        console.error('Failed to load current user:', err);
      }
    });
  }

  loadAllProjects(): void {
    this.elnService.getProjects().subscribe({
      next: (response) => {
        if (response.success && response.projects) {
          this.allProjects = response.projects;
        }
      },
      error: (err) => {
        console.error('Failed to load projects:', err);
      }
    });
  }

  loadUser(): void {
    if (!this.userId) return;
    
    this.loading = true;
    this.elnService.getUser(this.userId).subscribe({
      next: (response) => {
        if (response.success && response.user) {
          this.user = response.user;
          this.populateForm();
          this.assignedProjects = this.user.projects || [];
          this.loadUserActivity();
        } else {
          this.error = response.error || 'Failed to load user';
        }
        this.loading = false;
      },
      error: (err) => {
        this.error = err.message || 'Failed to load user';
        this.loading = false;
      }
    });
  }

  loadUserActivity(): void {
    if (!this.userId) return;
    
    this.elnService.getUserActivity(this.userId).subscribe({
      next: (response) => {
        if (response.success && response.activities) {
          this.activityHistory = response.activities;
        } else {
          console.error('Failed to load user activity');
        }
      },
      error: (err) => {
        console.error('Failed to load user activity:', err);
      }
    });
  }

  populateForm(): void {
    if (!this.user) return;
    
    this.userForm.patchValue({
      name: this.user.name,
      email: this.user.email,
      role: this.user.role,
      department: this.user.department || '',
      title: this.user.title || '',
      phone: this.user.phone || '',
      status: this.user.status || 'active'
    });
    
    // Remove password validators for existing users in edit mode
    if (!this.isNewUser) {
      this.userForm.get('password')?.clearValidators();
      this.userForm.get('password')?.updateValueAndValidity();
    }
  }

  passwordMatchValidator(form: FormGroup): { [key: string]: boolean } | null {
    const password = form.get('password');
    const confirmPassword = form.get('confirmPassword');
    
    // If we're not setting a password, don't validate
    if (!password?.value) {
      return null;
    }
    
    if (password?.value !== confirmPassword?.value) {
      return { 'passwordMismatch': true };
    }
    
    return null;
  }

  toggleEditMode(): void {
    this.editMode = !this.editMode;
    if (!this.editMode) {
      this.populateForm();
    }
  }

  saveUser(): void {
    if (this.userForm.invalid) {
      this.markFormGroupTouched(this.userForm);
      this.snackBar.open('Please fill in all required fields correctly', 'Close', {
        duration: 5000
      });
      return;
    }
    
    const userData = { ...this.userForm.value };
    
    // Don't send confirmPassword to API
    delete userData.confirmPassword;
    
    // Don't send empty password
    if (!userData.password) {
      delete userData.password;
    }
    
    this.saving = true;
    
    if (this.isNewUser) {
      this.elnService.createUser(userData).subscribe({
        next: (response) => {
          if (response.success && response.user) {
            this.snackBar.open('User created successfully', 'Close', {
              duration: 3000
            });
            this.router.navigate(['/eln/users', response.user.id]);
          } else {
            this.snackBar.open(response.error || 'Failed to create user', 'Close', {
              duration: 5000
            });
          }
          this.saving = false;
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to create user', 'Close', {
            duration: 5000
          });
          this.saving = false;
        }
      });
    } else if (this.userId) {
      this.elnService.updateUser(this.userId, userData).subscribe({
        next: (response) => {
          if (response.success && response.user) {
            this.user = response.user;
            this.editMode = false;
            this.snackBar.open('User updated successfully', 'Close', {
              duration: 3000
            });
          } else {
            this.snackBar.open(response.error || 'Failed to update user', 'Close', {
              duration: 5000
            });
          }
          this.saving = false;
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to update user', 'Close', {
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
      }
    });
  }

  toggleUserStatus(): void {
    if (!this.user) return;
    
    const newStatus = this.user.status === 'active' ? 'inactive' : 'active';
    
    // Don't allow deactivating yourself
    if (this.currentUser && this.currentUser.id === this.user.id && newStatus === 'inactive') {
      this.snackBar.open('You cannot deactivate your own account', 'Close', {
        duration: 5000
      });
      return;
    }
    
    this.elnService.updateUserStatus(this.user.id, newStatus).subscribe({
      next: (response) => {
        if (response.success && response.user) {
          this.user = response.user;
          this.snackBar.open(`User ${newStatus === 'active' ? 'activated' : 'deactivated'} successfully`, 'Close', {
            duration: 3000
          });
        } else {
          this.snackBar.open(response.error || 'Failed to update user status', 'Close', {
            duration: 5000
          });
        }
      },
      error: (err) => {
        this.snackBar.open(err.message || 'Failed to update user status', 'Close', {
          duration: 5000
        });
      }
    });
  }

  deleteUser(): void {
    if (!this.user) return;
    
    // Don't allow deleting yourself
    if (this.currentUser && this.currentUser.id === this.user.id) {
      this.snackBar.open('You cannot delete your own account', 'Close', {
        duration: 5000
      });
      return;
    }
    
    if (confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
      this.elnService.deleteUser(this.user.id).subscribe({
        next: (response) => {
          if (response.success) {
            this.snackBar.open('User deleted successfully', 'Close', {
              duration: 3000
            });
            this.router.navigate(['/eln/users']);
          } else {
            this.snackBar.open(response.error || 'Failed to delete user', 'Close', {
              duration: 5000
            });
          }
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to delete user', 'Close', {
            duration: 5000
          });
        }
      });
    }
  }

  assignProject(project: Project): void {
    if (!this.user || !this.userId) return;
    
    this.elnService.assignUserToProject(this.userId, project.id).subscribe({
      next: (response) => {
        if (response.success) {
          if (!this.assignedProjects.find(p => p.id === project.id)) {
            this.assignedProjects.push(project);
          }
          this.snackBar.open(`User assigned to ${project.name} successfully`, 'Close', {
            duration: 3000
          });
        } else {
          this.snackBar.open(response.error || 'Failed to assign user to project', 'Close', {
            duration: 5000
          });
        }
      },
      error: (err) => {
        this.snackBar.open(err.message || 'Failed to assign user to project', 'Close', {
          duration: 5000
        });
      }
    });
  }

  removeFromProject(project: Project): void {
    if (!this.user || !this.userId) return;
    
    this.elnService.removeUserFromProject(this.userId, project.id).subscribe({
      next: (response) => {
        if (response.success) {
          this.assignedProjects = this.assignedProjects.filter(p => p.id !== project.id);
          this.snackBar.open(`User removed from ${project.name} successfully`, 'Close', {
            duration: 3000
          });
        } else {
          this.snackBar.open(response.error || 'Failed to remove user from project', 'Close', {
            duration: 5000
          });
        }
      },
      error: (err) => {
        this.snackBar.open(err.message || 'Failed to remove user from project', 'Close', {
          duration: 5000
        });
      }
    });
  }

  isProjectAssigned(project: Project): boolean {
    return this.assignedProjects.some(p => p.id === project.id);
  }

  getUnassignedProjects(): Project[] {
    return this.allProjects.filter(project => 
      !this.assignedProjects.some(p => p.id === project.id)
    );
  }

  getRoleBadgeClass(role: string): string {
    switch (role.toLowerCase()) {
      case 'admin':
        return 'role-admin';
      case 'manager':
        return 'role-manager';
      case 'scientist':
        return 'role-scientist';
      case 'technician':
        return 'role-technician';
      case 'viewer':
        return 'role-viewer';
      default:
        return 'role-default';
    }
  }

  getStatusBadgeClass(status: string): string {
    return status === 'active' ? 'status-active' : 'status-inactive';
  }

  canManageUser(): boolean {
    if (!this.user || !this.currentUser) return false;
    
    // Admin can manage all users except themselves
    if (this.currentUser.role === 'admin') {
      return this.currentUser.id !== this.user.id;
    }
    
    // Manager can manage scientists, technicians, and viewers
    if (this.currentUser.role === 'manager') {
      return ['scientist', 'technician', 'viewer'].includes(this.user.role);
    }
    
    return false;
  }

  canEditUser(): boolean {
    if (!this.user || !this.currentUser) return false;
    
    // Admin can edit all users
    if (this.currentUser.role === 'admin') {
      return true;
    }
    
    // Manager can edit scientists, technicians, and viewers
    if (this.currentUser.role === 'manager') {
      return ['scientist', 'technician', 'viewer'].includes(this.user.role);
    }
    
    // Users can edit their own profile
    return this.currentUser.id === this.user.id;
  }
}
