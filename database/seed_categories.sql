INSERT INTO categories(name) VALUES
('Организация работы'), ('Документация'), ('Разработка'), ('Прочее')
ON CONFLICT (name) DO NOTHING;
