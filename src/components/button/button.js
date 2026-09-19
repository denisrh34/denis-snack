/**
 * Button Component Behavior
 * Handles loading states, keyboard interaction
 */

class ButtonComponent {
  constructor(element) {
    this.element = element;
    this.originalContent = null;
    this.bindEvents();
  }

  bindEvents() {
    // Keyboard activation for Enter/Space
    this.element.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        this.element.click();
      }
    });

    // Prevent form submit if button has type="button"
    if (this.element.type === 'button') {
      this.element.addEventListener('click', (e) => {
        if (this.element.disabled) e.preventDefault();
      });
    }
  }

  setLoading(loading) {
    if (loading) {
      if (!this.originalContent) {
        this.originalContent = this.element.innerHTML;
      }
      this.element.disabled = true;
      this.element.setAttribute('aria-busy', 'true');
      this.element.innerHTML = this.originalContent.replace(
        '<span class="btn-label">',
        '<span class="btn-spinner" aria-hidden="true">⟳</span><span class="btn-label">'
      );
    } else {
      this.element.disabled = false;
      this.element.setAttribute('aria-busy', 'false');
      if (this.originalContent) {
        this.element.innerHTML = this.originalContent;
        this.originalContent = null;
      }
    }
  }

  static init(selector = '.btn') {
    document.querySelectorAll(selector).forEach(el => new ButtonComponent(el));
  }
}

// Auto-init on DOM ready
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    ButtonComponent.init();
  });
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ButtonComponent;
}