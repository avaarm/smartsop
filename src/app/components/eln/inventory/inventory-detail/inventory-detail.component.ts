import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { ElnService, InventoryItem } from '../../../../services/eln-service.service';
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
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule } from '@angular/material/paginator';

@Component({
  selector: 'app-inventory-detail',
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
    MatChipsModule,
    MatDividerModule,
    MatTooltipModule,
    MatTableModule,
    MatPaginatorModule
  ],
  providers: [MatSnackBar],
  templateUrl: './inventory-detail.component.html',
  styleUrls: ['./inventory-detail.component.scss']
})
export class InventoryDetailComponent implements OnInit {
  itemId: string | null = null;
  item: InventoryItem | null = null;
  itemForm: FormGroup;
  isNewItem = false;
  loading = true;
  saving = false;
  error = '';
  editMode = false;
  
  // Usage history
  usageHistory: any[] = [];
  displayedColumns: string[] = ['date', 'experiment', 'user', 'quantity', 'notes'];
  
  // Categories and locations for dropdowns
  categories: string[] = [];
  locations: string[] = [];

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private elnService: ElnService,
    private fb: FormBuilder,
    private snackBar: MatSnackBar
  ) {
    this.itemForm = this.fb.group({
      name: ['', [Validators.required]],
      description: [''],
      category: [''],
      location: [''],
      quantity: [0, [Validators.required, Validators.min(0)]],
      min_quantity: [0, [Validators.required, Validators.min(0)]],
      unit: [''],
      catalog_number: [''],
      supplier: [''],
      price: [null],
      purchase_date: [null],
      expiration_date: [null],
      storage_conditions: [''],
      safety_notes: [''],
      attachments: ['']
    });
  }

  ngOnInit(): void {
    this.loadCategoriesAndLocations();
    
    this.route.paramMap.subscribe(params => {
      this.itemId = params.get('id');
      
      if (this.itemId === 'new') {
        this.isNewItem = true;
        this.editMode = true;
        this.loading = false;
      } else if (this.itemId) {
        this.loadInventoryItem();
      }
    });
  }

  loadInventoryItem(): void {
    if (!this.itemId) return;
    
    this.loading = true;
    this.elnService.getInventoryItem(this.itemId).subscribe({
      next: (response) => {
        if (response.success && response.item) {
          this.item = response.item;
          this.populateForm();
          this.loadUsageHistory();
        } else {
          this.error = response.error || 'Failed to load inventory item';
        }
        this.loading = false;
      },
      error: (err) => {
        this.error = err.message || 'Failed to load inventory item';
        this.loading = false;
      }
    });
  }

  loadCategoriesAndLocations(): void {
    // Load categories
    this.elnService.getInventoryCategories().subscribe({
      next: (response) => {
        if (response.success && response.categories) {
          this.categories = response.categories;
        }
      },
      error: (err) => {
        console.error('Failed to load categories:', err);
      }
    });
    
    // Load locations
    this.elnService.getInventoryLocations().subscribe({
      next: (response) => {
        if (response.success && response.locations) {
          this.locations = response.locations;
        }
      },
      error: (err) => {
        console.error('Failed to load locations:', err);
      }
    });
  }

  loadUsageHistory(): void {
    if (!this.itemId) return;
    
    this.elnService.getInventoryItemUsageHistory(this.itemId).subscribe({
      next: (response) => {
        if (response.success && response.history) {
          this.usageHistory = response.history;
        } else {
          console.error('Failed to load usage history');
        }
      },
      error: (err) => {
        console.error('Failed to load usage history:', err);
      }
    });
  }

  populateForm(): void {
    if (!this.item) return;
    
    this.itemForm.patchValue({
      name: this.item.name,
      description: this.item.description || '',
      category: this.item.category || '',
      location: this.item.location || '',
      quantity: this.item.quantity,
      min_quantity: this.item.min_quantity,
      unit: this.item.unit || '',
      catalog_number: this.item.catalog_number || '',
      supplier: this.item.supplier || '',
      price: this.item.price || null,
      purchase_date: this.item.purchase_date ? new Date(this.item.purchase_date) : null,
      expiration_date: this.item.expiration_date ? new Date(this.item.expiration_date) : null,
      storage_conditions: this.item.storage_conditions || '',
      safety_notes: this.item.safety_notes || '',
      attachments: this.item.attachments || ''
    });
  }

  toggleEditMode(): void {
    this.editMode = !this.editMode;
    if (!this.editMode) {
      this.populateForm();
    }
  }

  saveInventoryItem(): void {
    if (this.itemForm.invalid) {
      this.markFormGroupTouched(this.itemForm);
      this.snackBar.open('Please fill in all required fields', 'Close', {
        duration: 5000
      });
      return;
    }
    
    const itemData = this.itemForm.value;
    
    this.saving = true;
    
    if (this.isNewItem) {
      this.elnService.createInventoryItem(itemData).subscribe({
        next: (response) => {
          if (response.success && response.item) {
            this.snackBar.open('Inventory item created successfully', 'Close', {
              duration: 3000
            });
            this.router.navigate(['/eln/inventory', response.item.id]);
          } else {
            this.snackBar.open(response.error || 'Failed to create inventory item', 'Close', {
              duration: 5000
            });
          }
          this.saving = false;
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to create inventory item', 'Close', {
            duration: 5000
          });
          this.saving = false;
        }
      });
    } else if (this.itemId) {
      this.elnService.updateInventoryItem(this.itemId, itemData).subscribe({
        next: (response) => {
          if (response.success && response.item) {
            this.item = response.item;
            this.editMode = false;
            this.snackBar.open('Inventory item updated successfully', 'Close', {
              duration: 3000
            });
          } else {
            this.snackBar.open(response.error || 'Failed to update inventory item', 'Close', {
              duration: 5000
            });
          }
          this.saving = false;
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to update inventory item', 'Close', {
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

  updateQuantity(change: number): void {
    if (!this.item) return;
    
    const newQuantity = this.item.quantity + change;
    if (newQuantity < 0) {
      this.snackBar.open('Quantity cannot be negative', 'Close', {
        duration: 3000
      });
      return;
    }
    
    this.elnService.updateInventoryItemQuantity(this.item.id, newQuantity).subscribe({
      next: (response) => {
        if (response.success && response.item) {
          this.item = response.item;
          this.populateForm();
          this.snackBar.open('Quantity updated successfully', 'Close', {
            duration: 3000
          });
        } else {
          this.snackBar.open(response.error || 'Failed to update quantity', 'Close', {
            duration: 5000
          });
        }
      },
      error: (err) => {
        this.snackBar.open(err.message || 'Failed to update quantity', 'Close', {
          duration: 5000
        });
      }
    });
  }

  getItemStatus(): string {
    if (!this.item) return 'default';
    
    if (this.item.quantity <= 0) {
      return 'out';
    } else if (this.item.min_quantity && this.item.quantity <= this.item.min_quantity) {
      return 'low';
    } else {
      return 'ok';
    }
  }

  getStatusText(): string {
    const status = this.getItemStatus();
    
    if (status === 'out') {
      return 'Out of Stock';
    } else if (status === 'low') {
      return 'Low Stock';
    } else {
      return 'In Stock';
    }
  }

  isExpired(): boolean {
    if (!this.item || !this.item.expiration_date) return false;
    
    const today = new Date();
    const expirationDate = new Date(this.item.expiration_date);
    
    return expirationDate < today;
  }

  getDaysUntilExpiration(): number {
    if (!this.item || !this.item.expiration_date) return 0;
    
    const today = new Date();
    const expirationDate = new Date(this.item.expiration_date);
    const diffTime = expirationDate.getTime() - today.getTime();
    
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  }
}
