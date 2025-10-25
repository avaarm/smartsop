import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ElnService, User } from '../../../../services/eln-service.service';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatSortModule, Sort } from '@angular/material/sort';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { MatDialogModule } from '@angular/material/dialog';

@Component({
  selector: 'app-user-list',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatSelectModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatTableModule,
    MatPaginatorModule,
    MatSortModule,
    MatChipsModule,
    MatTooltipModule,
    MatMenuModule,
    MatDialogModule
  ],
  providers: [MatSnackBar],
  templateUrl: './user-list.component.html',
  styleUrls: ['./user-list.component.scss']
})
export class UserListComponent implements OnInit {
  users: User[] = [];
  filteredUsers: User[] = [];
  displayedUsers: User[] = [];
  loading = true;
  error = '';
  currentUser: User | null = null;
  
  // Table columns
  displayedColumns: string[] = ['name', 'email', 'role', 'status', 'projects', 'actions'];
  
  // Filter options
  roleFilter = 'all';
  statusFilter = 'all';
  searchQuery = '';
  
  // Pagination
  pageSize = 10;
  pageSizeOptions = [5, 10, 25, 50];
  pageIndex = 0;
  totalUsers = 0;

  constructor(
    private elnService: ElnService,
    private snackBar: MatSnackBar
  ) { }

  ngOnInit(): void {
    this.loadCurrentUser();
    this.loadUsers();
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

  loadUsers(): void {
    this.loading = true;
    
    this.elnService.getUsers().subscribe({
      next: (response) => {
        if (response.success && response.users) {
          this.users = response.users;
          this.applyFilters();
        } else {
          this.error = 'Failed to load users';
        }
        this.loading = false;
      },
      error: (err) => {
        this.error = err.message || 'Failed to load users';
        this.loading = false;
      }
    });
  }

  applyFilters(): void {
    this.filteredUsers = this.users.filter(user => {
      // Apply role filter
      if (this.roleFilter !== 'all' && user.role !== this.roleFilter) {
        return false;
      }
      
      // Apply status filter
      if (this.statusFilter !== 'all' && user.status !== this.statusFilter) {
        return false;
      }
      
      // Apply search query filter
      if (this.searchQuery && !this.matchesSearchQuery(user)) {
        return false;
      }
      
      return true;
    });
    
    // Update pagination
    this.totalUsers = this.filteredUsers.length;
    this.updateDisplayedUsers();
  }

  matchesSearchQuery(user: User): boolean {
    const query = this.searchQuery.toLowerCase();
    return Boolean(
      user.name.toLowerCase().includes(query) ||
      user.email.toLowerCase().includes(query) ||
      (user.department && user.department.toLowerCase().includes(query))
    );
  }

  onFilterChange(): void {
    this.pageIndex = 0;
    this.applyFilters();
  }

  onSearchQueryChange(): void {
    this.pageIndex = 0;
    this.applyFilters();
  }

  onPageChange(event: PageEvent): void {
    this.pageIndex = event.pageIndex;
    this.pageSize = event.pageSize;
    this.updateDisplayedUsers();
  }

  onSort(sort: Sort): void {
    const data = [...this.filteredUsers];
    
    if (!sort.active || sort.direction === '') {
      this.filteredUsers = data;
    } else {
      this.filteredUsers = data.sort((a, b) => {
        const isAsc = sort.direction === 'asc';
        switch (sort.active) {
          case 'name': return this.compare(a.name, b.name, isAsc);
          case 'email': return this.compare(a.email, b.email, isAsc);
          case 'role': return this.compare(a.role, b.role, isAsc);
          case 'status': return this.compare(a.status, b.status, isAsc);
          default: return 0;
        }
      });
    }
    
    this.updateDisplayedUsers();
  }

  compare(a: string | number, b: string | number, isAsc: boolean): number {
    return (a < b ? -1 : 1) * (isAsc ? 1 : -1);
  }

  updateDisplayedUsers(): void {
    const startIndex = this.pageIndex * this.pageSize;
    this.displayedUsers = this.filteredUsers.slice(startIndex, startIndex + this.pageSize);
  }

  toggleUserStatus(event: Event, userId: string, newStatus: string): void {
    event.stopPropagation();
    
    // Don't allow deactivating yourself
    if (this.currentUser && this.currentUser.id === userId && newStatus === 'inactive') {
      this.snackBar.open('You cannot deactivate your own account', 'Close', {
        duration: 5000
      });
      return;
    }
    
    this.elnService.updateUserStatus(userId, newStatus).subscribe({
      next: (response) => {
        if (response.success && response.user) {
          // Update user in lists
          const updatedUser = response.user;
          const index = this.users.findIndex(u => u.id === userId);
          if (index !== -1) {
            this.users[index] = updatedUser;
          }
          
          this.applyFilters();
          
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

  deleteUser(event: Event, userId: string): void {
    event.stopPropagation();
    
    // Don't allow deleting yourself
    if (this.currentUser && this.currentUser.id === userId) {
      this.snackBar.open('You cannot delete your own account', 'Close', {
        duration: 5000
      });
      return;
    }
    
    if (confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
      this.elnService.deleteUser(userId).subscribe({
        next: (response) => {
          if (response.success) {
            this.users = this.users.filter(u => u.id !== userId);
            this.applyFilters();
            this.snackBar.open('User deleted successfully', 'Close', {
              duration: 3000
            });
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

  canManageUser(user: User): boolean {
    // Admin can manage all users except themselves
    if (this.currentUser && this.currentUser.role === 'admin') {
      return this.currentUser.id !== user.id;
    }
    
    // Manager can manage scientists, technicians, and viewers
    if (this.currentUser && this.currentUser.role === 'manager') {
      return ['scientist', 'technician', 'viewer'].includes(user.role);
    }
    
    return false;
  }
}
