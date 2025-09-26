document.addEventListener('DOMContentLoaded', function () {
    const userList = document.getElementById('userTableBody');
    const prevPageBtn = document.getElementById('prevPage');
    const nextPageBtn = document.getElementById('nextPage');
    const pageNumbers = document.getElementById('pageNumbers');
    const addUserBtn = document.getElementById('addUserBtn');
    const userModalEl = document.getElementById('userModal');
    const userModal = new bootstrap.Modal(userModalEl);
    const userForm = document.getElementById('userForm');
    const userModalTitle = document.getElementById('modalTitle');

    let currentPage = 1;
    let totalPages = 1;
    const aPI_ENDPOINT = '/user-management/api';

    async function fetchUsers(page = 1) {
        try {
            const response = await fetch(`${aPI_ENDPOINT}/users?page=${page}`);
            if (!response.ok) {
                throw new Error('获取用户列表失败');
            }
            const data = await response.json();
            renderUsers(data.users);
            renderPagination(data.pagination);
            currentPage = page;
            totalPages = data.pagination.pages;
        } catch (error) {
            console.error(error);
            userList.innerHTML = `<tr><td colspan="7" class="text-center py-10 text-red-500">加载用户数据失败: ${error.message}</td></tr>`;
        }
    }

    function renderUsers(users) {
        userList.innerHTML = '';
        if (!users || users.length === 0) {
            userList.innerHTML = `<tr><td colspan="6" class="text-center py-4">没有找到用户。</td></tr>`;
            return;
        }
        users.forEach(user => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-3 py-2">${user.username}</td>
                <td class="px-3 py-2">${user.email}</td>
                <td class="px-3 py-2">${user.role || '未分配'}</td>
                <td class="px-3 py-2">
                    <span class="badge ${user.is_active ? 'bg-success' : 'bg-danger'}">${user.is_active ? '激活' : '禁用'}</span>
                </td>
                <td class="px-3 py-2">${new Date(user.created_at).toLocaleString()}</td>
                <td class="px-3 py-2 text-center">
                    <div class="btn-group btn-group-sm" role="group">
                        <button class="btn btn-outline-primary btn-sm edit-btn" data-id="${user.id}" title="编辑">
                            <i class='bx bx-edit'></i>
                        </button>
                        <button class="btn btn-outline-danger btn-sm delete-btn" data-id="${user.id}" title="删除">
                            <i class='bx bx-trash'></i>
                        </button>
                    </div>
                </td>
            `;
            userList.appendChild(tr);
        });
    }

    function renderPagination(pagination) {
        // 更新分页信息显示
        document.getElementById('startItem').textContent = ((pagination.page - 1) * pagination.per_page + 1);
        document.getElementById('endItem').textContent = Math.min(pagination.page * pagination.per_page, pagination.total);
        document.getElementById('totalItems').textContent = pagination.total;

        // 更新上一页按钮
        const prevPageItem = document.getElementById('prevPageItem');
        if (pagination.has_prev) {
            prevPageItem.classList.remove('disabled');
            prevPageBtn.disabled = false;
        } else {
            prevPageItem.classList.add('disabled');
            prevPageBtn.disabled = true;
        }

        // 更新下一页按钮
        const nextPageItem = document.getElementById('nextPageItem');
        if (pagination.has_next) {
            nextPageItem.classList.remove('disabled');
            nextPageBtn.disabled = false;
        } else {
            nextPageItem.classList.add('disabled');
            nextPageBtn.disabled = true;
        }

        // 生成页码按钮
        pageNumbers.innerHTML = '';
        const startPage = Math.max(1, pagination.page - 2);
        const endPage = Math.min(pagination.pages, pagination.page + 2);

        for (let i = startPage; i <= endPage; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === pagination.page ? 'active' : ''}`;
            li.innerHTML = `<button class="page-link" data-page="${i}">${i}</button>`;
            pageNumbers.appendChild(li);
        }
    }

    function openModal(mode, user = null) {
        userForm.reset();
        document.getElementById('userId').value = '';
        const passwordInput = document.getElementById('password');

        if (mode === 'add') {
            userModalTitle.textContent = '添加新用户';
            passwordInput.setAttribute('required', 'required');
        } else {
            userModalTitle.textContent = '编辑用户';
            document.getElementById('userId').value = user.id;
            document.getElementById('username').value = user.username;
            document.getElementById('email').value = user.email;
            document.getElementById('role').value = user.role_type;
            document.getElementById('isActive').checked = user.is_active;
            passwordInput.removeAttribute('required');
        }
        userModal.show();
    }

    async function handleFormSubmit(event) {
        event.preventDefault();
        const userId = document.getElementById('userId').value;
        const url = userId ? `${aPI_ENDPOINT}/users/${userId}` : `${aPI_ENDPOINT}/users`;
        const method = userId ? 'PUT' : 'POST';
        const password = document.getElementById('password').value;

        const data = {
            username: document.getElementById('username').value,
            email: document.getElementById('email').value,
            role: document.getElementById('role').value,
            is_active: document.getElementById('isActive').checked,
        };

        if (password) {
            data.password = password;
        }

        try {
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '保存用户失败');
            }

            userModal.hide();
            fetchUsers(currentPage);
            // 在这里可以添加一个成功提示
        } catch (error) {
            console.error(error);
            alert(`错误: ${error.message}`);
        }
    }

    // 分页事件监听器
    prevPageBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            fetchUsers(currentPage - 1);
        }
    });

    nextPageBtn.addEventListener('click', () => {
        // 假设totalPages在fetchUsers中被设置
        if (currentPage < totalPages) {
            fetchUsers(currentPage + 1);
        }
    });

    pageNumbers.addEventListener('click', (event) => {
        if (event.target.classList.contains('page-link')) {
            const page = parseInt(event.target.dataset.page, 10);
            if (page && page !== currentPage) {
                fetchUsers(page);
            }
        }
    });

    addUserBtn.addEventListener('click', () => openModal('add'));
    userForm.addEventListener('submit', handleFormSubmit);

    userList.addEventListener('click', async (event) => {
        const target = event.target.closest('button');
        if (!target) return;

        const userId = target.dataset.id;

        if (target.classList.contains('edit-btn')) {
            try {
                const response = await fetch(`${aPI_ENDPOINT}/users/${userId}`);
                if (!response.ok) {
                    throw new Error('获取用户信息失败');
                }
                const user = await response.json();
                openModal('edit', user);
            } catch (error) {
                console.error(error);
                alert(`错误: ${error.message}`);
            }
        }

        if (target.classList.contains('delete-btn')) {
            if (confirm('确定要删除此用户吗？')) {
                try {
                    const response = await fetch(`${aPI_ENDPOINT}/users/${userId}`, {
                        method: 'DELETE',
                    });
                    if (!response.ok) {
                        throw new Error('删除用户失败');
                    }
                    fetchUsers(currentPage);
                } catch (error) {
                    console.error(error);
                    alert(`错误: ${error.message}`);
                }
            }
        }
    });

    fetchUsers();
});