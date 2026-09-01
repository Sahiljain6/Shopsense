export default function UserProfileMenu({ authed, onLogout }) {
  if (!authed) return null;

  return (
    <div className="navbar-user-cluster">
      <button
        className="navbar-logout-btn fastshot-logout-btn"
        type="button"
        onClick={onLogout}
        title="Sign out of ShopSense"
      >
        Log out
      </button>
    </div>
  );
}
