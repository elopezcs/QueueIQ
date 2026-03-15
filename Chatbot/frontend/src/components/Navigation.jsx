import React, { useEffect, useMemo, useRef, useState } from 'react';

function dashboardItemsForRole(role) {
  const normalizedRole = String(role || '').toLowerCase();
  if (normalizedRole === 'staff') {
    return [
      { id: 'dashboard', label: 'Dashboard' },
      { id: 'profile', label: 'Profile' },
      { id: 'logout', label: 'Logout' },
    ];
  }
  if (normalizedRole === 'manager') {
    return [
      { id: 'simulations', label: 'Simulations' },
      { id: 'add-member', label: 'Add Member' },
      { id: 'logout', label: 'Logout' },
    ];
  }
  return [
    { id: 'my-appointments', label: 'My Appointments' },
    { id: 'profile', label: 'Profile' },
    { id: 'logout', label: 'Logout' },
  ];
}

function isLargeScreenHoverEnabled() {
  return typeof window !== 'undefined' && window.matchMedia('(min-width: 769px)').matches;
}

export default function Navigation({
  currentPage,
  setCurrentPage,
  onHomeClick,
  currentUser,
  accountSection,
  onNavigateToAccountSection,
  onLogout,
}) {
  const [isDashboardOpen, setIsDashboardOpen] = useState(false);
  const dropdownRef = useRef(null);
  const closeTimerRef = useRef(null);
  const dashboardItems = useMemo(() => dashboardItemsForRole(currentUser?.role), [currentUser]);

  useEffect(() => {
    function handlePointer(event) {
      if (!dropdownRef.current || dropdownRef.current.contains(event.target)) {
        return;
      }
      setIsDashboardOpen(false);
    }

    function handleEscape(event) {
      if (event.key === 'Escape') {
        setIsDashboardOpen(false);
      }
    }

    document.addEventListener('mousedown', handlePointer);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handlePointer);
      document.removeEventListener('keydown', handleEscape);
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
      }
    };
  }, []);

  function cancelScheduledClose() {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }

  function scheduleClose() {
    cancelScheduledClose();
    closeTimerRef.current = setTimeout(() => {
      setIsDashboardOpen(false);
    }, 180);
  }

  function renderNavLink(label, page, onClick, isActiveOverride = null) {
    const isActive = isActiveOverride ?? currentPage === page;
    return (
      <a
        href="#"
        className={`nav-link ${isActive ? 'active' : ''}`}
        onClick={(event) => {
          event.preventDefault();
          onClick();
        }}
      >
        {label}
      </a>
    );
  }

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-logo" onClick={onHomeClick} style={{ cursor: 'pointer' }}>
          QueueIQ
        </div>
        <ul className="navbar-menu">
          <li>{renderNavLink('Home', 'home', () => setCurrentPage('home'))}</li>
          <li>{renderNavLink('About Us', 'about', () => setCurrentPage('about'))}</li>
          <li>{renderNavLink('Team', 'team', () => setCurrentPage('team'))}</li>
          <li>{renderNavLink('Privacy & Policy', 'privacy', () => setCurrentPage('privacy'))}</li>
          <li>{renderNavLink('Contact Us', 'contact', () => setCurrentPage('contact'))}</li>

          {currentUser ? (
            <li
              className="nav-dropdown-item"
              ref={dropdownRef}
              onMouseEnter={() => {
                if (isLargeScreenHoverEnabled()) {
                  cancelScheduledClose();
                  setIsDashboardOpen(true);
                }
              }}
              onMouseLeave={() => {
                if (isLargeScreenHoverEnabled()) {
                  scheduleClose();
                }
              }}
            >
              <a
                href="#"
                className={`nav-link nav-dropdown-toggle ${currentPage === 'account' ? 'active' : ''}`}
                onClick={(event) => {
                  event.preventDefault();
                  cancelScheduledClose();
                  setIsDashboardOpen((current) => !current);
                }}
              >
                Dashboard
                <span className={`nav-caret ${isDashboardOpen ? 'open' : ''}`} aria-hidden="true" />
              </a>
              {isDashboardOpen ? (
                <div
                  className="nav-dropdown-menu"
                  onMouseEnter={cancelScheduledClose}
                  onMouseLeave={() => {
                    if (isLargeScreenHoverEnabled()) {
                      scheduleClose();
                    }
                  }}
                >
                  {dashboardItems.map((item) => (
                    <a
                      key={item.id}
                      href="#"
                      className={`nav-dropdown-link ${currentPage === 'account' && accountSection === item.id ? 'active' : ''}`}
                      onClick={(event) => {
                        event.preventDefault();
                        cancelScheduledClose();
                        setIsDashboardOpen(false);
                        if (item.id === 'logout') {
                          onLogout();
                          return;
                        }
                        onNavigateToAccountSection(item.id);
                      }}
                    >
                      {item.label}
                    </a>
                  ))}
                </div>
              ) : null}
            </li>
          ) : (
            <li>{renderNavLink('Login / Register', 'account', () => onNavigateToAccountSection('auth'))}</li>
          )}
        </ul>
      </div>
    </nav>
  );
}
