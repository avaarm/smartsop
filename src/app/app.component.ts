import { Component } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive
  ]
})
export class AppComponent {
  isLoggedIn: boolean = false;
  
  login(): void {
    // Simulate login functionality
    this.isLoggedIn = true;
    console.log('User logged in');
  }
  
  logout(): void {
    // Simulate logout functionality
    this.isLoggedIn = false;
    console.log('User logged out');
  }
}
