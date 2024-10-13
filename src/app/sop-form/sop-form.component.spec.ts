import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SopFormComponent } from './sop-form.component';

describe('SopFormComponent', () => {
  let component: SopFormComponent;
  let fixture: ComponentFixture<SopFormComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SopFormComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SopFormComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
