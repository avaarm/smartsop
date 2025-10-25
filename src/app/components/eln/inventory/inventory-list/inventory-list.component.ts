import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ElnService, InventoryItem } from '../../../../services/eln-service.service';
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
import { MatBadgeModule } from '@angular/material/badge';
import { MatTooltipModule } from '@angular/material/tooltip';

@Component({
  selector: 'app-inventory-list',
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
    MatBadgeModule,
    MatTooltipModule
  ],
  providers: [MatSnackBar],
  templateUrl: './inventory-list.component.html',
  styleUrls: ['./inventory-list.component.scss']
})
export class InventoryListComponent implements OnInit {
  inventoryItems: InventoryItem[] = [];
  filteredItems: InventoryItem[] = [];
  displayedItems: InventoryItem[] = [];
  loading = true;
  error = '';
  
  // Table columns
  displayedColumns: string[] = ['name', 'category', 'location', 'quantity', 'status', 'actions'];
  
  // Filter options
  categoryFilter = 'all';
  locationFilter = 'all';
  statusFilter = 'all';
  searchQuery = '';
  
  // Categories and locations
  categories: string[] = [];
  locations: string[] = [];
  
  // Pagination
  pageSize = 10;
  pageSizeOptions = [5, 10, 25, 50];
  pageIndex = 0;
  totalItems = 0;

  constructor(
    private elnService: ElnService,
    private snackBar: MatSnackBar
  ) { }

  ngOnInit(): void {
    this.loadInventory();
  }

  loadInventory(): void {
    this.loading = true;
    
    this.elnService.getInventoryItems().subscribe({
      next: (response) => {
        if (response.success && response.items) {
          this.inventoryItems = response.items;
          this.extractFilters();
          this.applyFilters();
        } else {
          this.error = 'Failed to load inventory items';
        }
        this.loading = false;
      },
      error: (err) => {
        this.error = err.message || 'Failed to load inventory items';
        this.loading = false;
      }
    });
  }

  extractFilters(): void {
    // Extract unique categories and locations
    const categorySet = new Set<string>();
    const locationSet = new Set<string>();
    
    this.inventoryItems.forEach(item => {
      if (item.category) {
        categorySet.add(item.category);
      }
      if (item.location) {
        locationSet.add(item.location);
      }
    });
    
    this.categories = Array.from(categorySet);
    this.locations = Array.from(locationSet);
  }

  applyFilters(): void {
    this.filteredItems = this.inventoryItems.filter(item => {
      // Apply category filter
      if (this.categoryFilter !== 'all' && item.category !== this.categoryFilter) {
        return false;
      }
      
      // Apply location filter
      if (this.locationFilter !== 'all' && item.location !== this.locationFilter) {
        return false;
      }
      
      // Apply status filter
      if (this.statusFilter !== 'all') {
        if (this.statusFilter === 'low' && item.min_quantity && item.quantity > item.min_quantity) {
          return false;
        } else if (this.statusFilter === 'out' && item.quantity > 0) {
          return false;
        } else if (this.statusFilter === 'ok' && (item.min_quantity && item.quantity <= item.min_quantity || item.quantity <= 0)) {
          return false;
        }
      }
      
      // Apply search query filter
      if (this.searchQuery && !this.matchesSearchQuery(item)) {
        return false;
      }
      
      return true;
    });
    
    // Update pagination
    this.totalItems = this.filteredItems.length;
    this.updateDisplayedItems();
  }

  matchesSearchQuery(item: InventoryItem): boolean {
    const query = this.searchQuery.toLowerCase();
    return Boolean(
      item.name.toLowerCase().includes(query) ||
      (item.description && item.description.toLowerCase().includes(query)) ||
      (item.catalog_number && item.catalog_number.toLowerCase().includes(query)) ||
      (item.supplier && item.supplier.toLowerCase().includes(query)) ||
      (item.category && item.category.toLowerCase().includes(query)) ||
      (item.location && item.location.toLowerCase().includes(query))
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
    this.updateDisplayedItems();
  }

  onSort(sort: Sort): void {
    const data = [...this.filteredItems];
    
    if (!sort.active || sort.direction === '') {
      this.filteredItems = data;
    } else {
      this.filteredItems = data.sort((a, b) => {
        const isAsc = sort.direction === 'asc';
        switch (sort.active) {
          case 'name': return this.compare(a.name, b.name, isAsc);
          case 'category': return this.compare(a.category || '', b.category || '', isAsc);
          case 'location': return this.compare(a.location || '', b.location || '', isAsc);
          case 'quantity': return this.compare(a.quantity, b.quantity, isAsc);
          default: return 0;
        }
      });
    }
    
    this.updateDisplayedItems();
  }

  compare(a: string | number, b: string | number, isAsc: boolean): number {
    return (a < b ? -1 : 1) * (isAsc ? 1 : -1);
  }

  updateDisplayedItems(): void {
    const startIndex = this.pageIndex * this.pageSize;
    this.displayedItems = this.filteredItems.slice(startIndex, startIndex + this.pageSize);
  }

  getItemStatus(item: InventoryItem): string {
    if (item.quantity <= 0) {
      return 'out';
    } else if (item.min_quantity && item.quantity <= item.min_quantity) {
      return 'low';
    } else {
      return 'ok';
    }
  }

  deleteInventoryItem(event: Event, itemId: string): void {
    event.stopPropagation();
    
    if (confirm('Are you sure you want to delete this inventory item? This action cannot be undone.')) {
      this.elnService.deleteInventoryItem(itemId).subscribe({
        next: (response) => {
          if (response.success) {
            this.inventoryItems = this.inventoryItems.filter(item => item.id !== itemId);
            this.applyFilters();
            this.snackBar.open('Inventory item deleted successfully', 'Close', {
              duration: 3000
            });
          } else {
            this.snackBar.open(response.error || 'Failed to delete inventory item', 'Close', {
              duration: 5000
            });
          }
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to delete inventory item', 'Close', {
            duration: 5000
          });
        }
      });
    }
  }

  updateQuantity(event: Event, item: InventoryItem, change: number): void {
    event.stopPropagation();
    
    const newQuantity = item.quantity + change;
    if (newQuantity < 0) {
      this.snackBar.open('Quantity cannot be negative', 'Close', {
        duration: 3000
      });
      return;
    }
    
    this.elnService.updateInventoryItemQuantity(item.id, newQuantity).subscribe({
      next: (response) => {
        if (response.success && response.item) {
          // Update the item in the lists
          const updatedItem = response.item;
          const index = this.inventoryItems.findIndex(i => i.id === item.id);
          if (index !== -1) {
            this.inventoryItems[index] = updatedItem;
          }
          
          const filteredIndex = this.filteredItems.findIndex(i => i.id === item.id);
          if (filteredIndex !== -1) {
            this.filteredItems[filteredIndex] = updatedItem;
          }
          
          const displayedIndex = this.displayedItems.findIndex(i => i.id === item.id);
          if (displayedIndex !== -1) {
            this.displayedItems[displayedIndex] = updatedItem;
          }
          
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
}
