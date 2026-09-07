<?php

namespace Ordering;

final class CustomerDto
{
    public static function fromRow(array $row): self
    {
        $dto = new self();
        $dto->id = $row['customer_id'];
        $dto->name = $row['display_name'];
        return $dto;
    }
}
