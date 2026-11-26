import React from 'react';
function icon(paths:React.ReactNode){return function Icon(){return <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths}</svg>}}
export const DashboardOutlined=icon(<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>);
export const UserOutlined=icon(<><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></>);
export const TeamOutlined=icon(<><circle cx="9" cy="8" r="3"/><path d="M2 21v-2a7 7 0 0 1 14 0v2M16 5a3 3 0 0 1 0 6m2 3a6 6 0 0 1 4 5v2"/></>);
export const ClusterOutlined=icon(<><rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2" y="17" width="6" height="5" rx="1"/><rect x="16" y="17" width="6" height="5" rx="1"/><path d="M12 7v5H5v5m7-5h7v5"/></>);
export const HistoryOutlined=icon(<><circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/></>);
export const BookOutlined=icon(<><path d="M4 3h6a4 4 0 0 1 4 4v14a4 4 0 0 0-4-3H4zM14 7a4 4 0 0 1 4-4h2v15h-2a4 4 0 0 0-4 3"/></>);
export const LogoutOutlined=icon(<><path d="M11 4H4v16h7m3-12 5 4-5 4m5-4H8"/></>);
export const ReloadOutlined=icon(<><path d="M20 10a8 8 0 1 0-2 8M20 4v6h-6"/></>);
