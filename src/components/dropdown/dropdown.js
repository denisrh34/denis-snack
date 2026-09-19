/**
 * Dropdown Component Behavior
 * Handles keyboard navigation, focus management, positioning
 */

class DropdownComponent {
  constructor(dropdownElement) {
    this.dropdown = dropdownElement;
    this.trigger = dropdownElement.querySelector('[data-dropdown-trigger]');
    this.menu = dropdownElement.querySelector('.dropdown-menu');
    this.items = [];
    this.isOpen = false;
    this.bindEvents();
  }

  bindEvents() {
    if (!this.trigger || !this.menu) return;

    // Toggle on click
    this.trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggle();
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (this.isOpen && !this.dropdown.contains(e.target)) {
        this.close();
      }
    });

    // Keyboard navigation
    this.trigger.addEventListener('keydown', (e) => this.handleTriggerKeydown(e));
    this.menu.addEventListener('keydown', (e) => this.handleMenuKeydown(e));

    // Close on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
        this.trigger.focus();
      }
    });
  }

  handleTriggerKeydown(e) {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      this.open();
      this.focusFirstItem();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.open();
      this.focusLastItem();
    }
  }

  handleMenuKeydown(e) {
    const enabledItems = this.items.filter(item => !item.disabled);
    const currentIndex = enabledItems.findIndex(item => item === document.activeElement);

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const nextIndex = (currentIndex + 1) % enabledItems.length;
      enabledItems[nextIndex].focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prevIndex = (currentIndex - 1 + enabledItems.length) % enabledItems.length;
      enabledItems[prevIndex].focus();
    } else if (e.key === 'Home') {
      e.preventDefault();
      enabledItems[0].focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      enabledItems[enabledItems.length - 1].focus();
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      document.activeElement.click();
      this.close();
      this.trigger.focus();
    } else if (e.key === 'Tab') {
      this.close();
    } else if (e.key.length === 1) {
      // Type-ahead search
      this.typeAhead(e.key);
    }
  }

  typeAhead(char) {
    const searchChar = char.toLowerCase();
    const enabledItems = this.items.filter(item => !item.disabled);
    const currentIndex = enabledItems.findIndex(item => item === document.activeElement);
    const startIndex = (currentIndex + 1) % enabledItems.length;

    for (let i = 0; i < enabledItems.length; i++) {
      const index = (startIndex + i) % enabledItems.length;
      const label = enabledItems[index].textContent.trim().toLowerCase();
      if (label.startsWith(searchChar)) {
        enabledItems[index].focus();
        break;
      }
    }
  }

  open() {
    if (this.isOpen) return;
    this.isOpen = true;
    this.menu.hidden = false;
    this.trigger.setAttribute('aria-expanded', 'true');
    this.updateItems();
    this.positionMenu();
  }

  close() {
    if (!this.isOpen) return;
    this.isOpen = false;
    this.menu.hidden = true;
    this.trigger.setAttribute('aria-expanded', 'false');
  }

  toggle() {
    if (this.isOpen) this.close();
    else this.open();
  }

  updateItems() {
    this.items = Array.from(this.menu.querySelectorAll('.dropdown-item:not(.dropdown-item-disabled)'));
  }

  focusFirstItem() {
    this.updateItems();
    if (this.items.length > 0) this.items[0].focus();
  }

  focusLastItem() {
    this.updateItems();
    if (this.items.length > 0) this.items[this.items.length - 1].focus();
  }

  positionMenu() {
    // Basic positioning - could be enhanced with Popper.js
    const rect = this.trigger.getBoundingClientRect();
    const menuRect = this.menu.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Horizontal flip
    if (rect.left + menuRect.width > viewportWidth) {
      this.menu.style.left = 'auto';
      this.menu.style.right = '0';
    }

    // Vertical flip
    if (rect.bottom + menuRect.height > viewportHeight && rect.top > menuRect.height) {
      this.menu.style.top = 'auto';
      this.menu.style.bottom = '100%';
      this.menu.style.marginTop = '0';
      this.menu.style.marginBottom = '4px';
    }
  }

  static init(selector = '.dropdown') {
    document.querySelectorAll(selector).forEach(el => new DropdownComponent(el));
  }
}

// Auto-init
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    DropdownComponent.init();
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = DropdownComponent;
}