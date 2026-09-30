INSERT INTO categories(name) VALUES
('Организационные'), ('Документация'), ('Обслуживание'), ('Прочее')
ON CONFLICT (name) DO NOTHING;
